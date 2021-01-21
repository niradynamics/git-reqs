import os.path
import xlwt
import networkx as nx
from networkx.drawing.nx_pydot import to_pydot, graphviz_layout
from bokeh.io import output_file, show
from bokeh.models import (BoxSelectTool, BoxZoomTool, ResetTool, Ellipse, Circle, Text, EdgesAndLinkedNodes, HoverTool,
                          MultiLine, NodesAndLinkedEdges, Plot, Range1d, TapTool, StaticLayoutProvider)
from bokeh.palettes import Spectral4, RdGy6
from bokeh.plotting import figure, from_networkx
from bokeh.models import ColumnDataSource, LabelSet
import math

def convert_to_xls(reqmodule):
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('Reqs')

    for i, field in enumerate(reqmodule.fields):
        for k, req in enumerate(reqmodule.ordered_req_names):
            if field == "Req-Id":
                sheet.write(k+1, i, req)
            elif field in reqmodule.reqs.nodes[req].keys():
                sheet.write(k+1, i, reqmodule.reqs.nodes[req][field])

        sheet.write(0, i, field)
    workbook.save(reqmodule.module_path + "/" + reqmodule.module_prefix + ".xls")


def convert_to_markdown(reqmodule, hugo=False):
    md_file = open(reqmodule.module_path + "/" + reqmodule.module_prefix + ".md", 'w')
    if hugo:
        md_file.write('---\n'
                      'title: ' + os.path.basename(reqmodule.module_path) + '\n' 
                      'weight: 1\n'
                      'markup: mmark\n'
                       '---\n')
        
    for req in reqmodule.ordered_req_names:

        
        if 'Formatting' in reqmodule.reqs.nodes[req].keys():
            formatting = reqmodule.reqs.nodes[req]['Formatting']
        else:
            formatting = ''

        if formatting.startswith('Heading'):
            if '_' in formatting:
                heading_level = int(formatting.split('_')[1])
            else:
                heading_level = 1
            preformatting = '#'*heading_level
            description = ' ' + reqmodule.reqs.nodes[req]['Description']
            req_nr_format = '*[' + req + ']*'
            line_ending = '\n\n'
        elif 'Table' in formatting: 
            preformatting = '|'
            # Handle both |a|b|c| and a|b|c
            description = '|'.join([x for x in reqmodule.reqs.nodes[req]['Description'].split('|') if x])
            if 'Heading' in formatting:
                description += '| Req-Id |'
                description += '\n' + '|' + '|'.join(['-'*len(x) for x in description.split('|') if x])
            req_nr_format = '| *' + req + '*'
            line_ending = ' |\n'
        elif 'BulletList' in formatting: 
            if '_' in formatting:
                bullet_level = int(formatting.split('_')[1])
            else:
                bullet_level = 1
            preformatting = '  '*bullet_level + '- '
            description = reqmodule.reqs.nodes[req]['Description']
            req_nr_format = '*[' + req + ']*'
            line_ending = '\n\n'
        elif 'Italic' in formatting: 
            preformatting = ''
            description = '*' + reqmodule.reqs.nodes[req]['Description'] + '*'
            req_nr_format = '*[' + req + ']*'
            line_ending = '\n\n'
        else:
            preformatting = ''
            description = reqmodule.reqs.nodes[req]['Description']
            req_nr_format = '*[' + req + ']*'
            line_ending = '\n\n'

        md_text = preformatting + description
        if reqmodule.reqs.nodes[req]['Type'] == 'Requirement':
            md_text += ' ' + req_nr_format
        md_text += line_ending

        md_file.write(md_text) 
    md_file.close()


def create_report(project, reqmodule):
    md_file = open(reqmodule.module_path + "/" + reqmodule.module_prefix + "_report.md", 'w')

    for req in project.modules[reqmodule].ordered_req_names:

        md_file.write(project.reqs.nodes[req]['Description'] +
                      " [" + req + "]\n\n")

        subgraph, ancestors, descendants = project.get_related_reqs(req)
        roots = [v for v, d in subgraph.in_degree() if d == 0]
        leaves = [v for v, d in subgraph.out_degree() if d == 0]

        for node in subgraph.nodes.values():
            if 'color' not in node['non_stored_fields'].keys() or not node['color']:
                node['non_stored_fields']['color'] = 'gray'
            for key in list(node.keys()):
                node['color'] = node['non_stored_fields']['color']
                if key not in ['Description', 'color']:
                    node.pop(key)


        if len(subgraph) > 1:
            pos = nx.spiral_layout(subgraph)
            nx.draw(subgraph, pos=pos)

            dot = to_pydot(subgraph)
            desc_nodes = [req]
            if len(ancestors) < 3:
                desc_nodes.extend(ancestors)
            if len(descendants) < 3:
                desc_nodes.extend(descendants)

            for node_name in desc_nodes:
                print(node_name)
                node = dot.get_node(node_name)[0]
                if 'Description' in node.obj_dict['attributes'].keys():
                    Desc = node.obj_dict['attributes']['Description']
                    Desc = Desc[:100] + '...' if len(Desc) > 100 else Desc 
                    node.set_label(node_name + '\n' + Desc)
                
            dot.get_node(req)[0].set_color('blue')

            md_file.write('```{.graphviz caption="%s"}\n' % req)
            md_file.write(dot.to_string())
            md_file.write('```\n\n')

    md_file.close()

def draw_coverage_diagrams(reqmodule):
    only_reqs_subgraph = reqmodule.get_reqs_with_attr(('Type', 'Requirement'))
    reqs_test_testresult_subgraph = reqmodule.get_reqs_with_attr([('Type', 'Requirement'), ('Type', 'Testcase'), ('Type', 'Test-Result')])
    total_reqs = len(only_reqs_subgraph.nodes)
    tested_reqs = [n for n, r in only_reqs_subgraph.nodes.items()
                   if 'non_stored_fields' in r.keys()
                    and 'verifies_link_status' in r['non_stored_fields'].keys()
                    and r['non_stored_fields']['verifies_link_status'] > 0]
    full_tested_reqs = [n for n, r in only_reqs_subgraph.nodes.items()
                   if 'non_stored_fields' in r.keys()
                    and 'verifies_link_status' in r['non_stored_fields'].keys()
                    and r['non_stored_fields']['verifies_link_status'] > 1]
    untested_reqs = [n for n, r in only_reqs_subgraph.nodes.items()
                   if n not in tested_reqs]

    passed_reqs = 0
    failed_reqs = 0


    for req in tested_reqs:
        subgraph, ancestors, descendants = reqmodule.get_related_reqs(req, reqs_test_testresult_subgraph)
        leaves = [v for v, d in subgraph.out_degree() if d == 0]
        passed = 0
        failed = 0
        for leaf in leaves:
            if 'Type' in subgraph.nodes[leaf].keys() and subgraph.nodes[leaf]['Type'] == 'Test-Result':
                if subgraph.nodes[leaf]['result'] == 'Passed':
                    passed += 1
                else:
                    failed += 1
        if passed == len(leaves) and req in full_tested_reqs:
            passed_reqs += 1
        elif failed > 0:
            failed_reqs += 1

    # file to save the model
    output_file(reqmodule.module_path + "/" + reqmodule.module_prefix + "_TestCoverage.html")

    # instantiating the figure object
    graph = figure(title="Test Coverage")

    # name of the sectors
    sectors = ["Passed", "Failed", "Linked to full test coverage", "Partly tested", "Untested"]

    # % tage weightage of the sectors
    parts = [passed_reqs/total_reqs,
             failed_reqs/total_reqs,
             len(full_tested_reqs)/total_reqs,
             len(tested_reqs)/total_reqs,
             len(untested_reqs)/total_reqs]

    # converting into radians
    radians = [math.radians(part * 360) for part in parts]

    # starting angle values
    start_angle = [math.radians(0)]
    prev = start_angle[0]
    for i in radians[:-1]:
        start_angle.append(i + prev)
        prev = i + prev

        # ending angle values
    end_angle = start_angle[1:] + [math.radians(0)]

    # center of the pie chart
    x = 0
    y = 0

    # radius of the glyphs
    radius = 1

    # color of the wedges
    color = ["green", "red", "lightblue", "lightgrey", "grey"]

    # plotting the graph
    for i in range(len(sectors)):
        graph.wedge(x, y, radius,
                    start_angle=start_angle[i],
                    end_angle=end_angle[i],
                    color=color[i],
                    legend_label=sectors[i])

        # displaying the graph
    show(graph)


def draw_bokeh(reqmodule, req=None):
    color_mapper = {'black': RdGy6[1], 'gray': RdGy6[2], 'red': Spectral4[3], 'green': Spectral4[1]}
    colors = []
    special_pos = {}
    if req:
        G, ancestors, descendants = reqmodule.get_related_reqs(req)
    else:
        G = reqmodule.reqs
        for moduleName, module in reqmodule.modules.items():
            moduleOnly = nx.subgraph(G, module.ordered_req_names)
            roots = [v for v, d in moduleOnly.in_degree() if d == 0]
            G.add_node(moduleName)
            # Put the spec name node a bit lower to make the graph nicer
            special_pos[moduleName] = (0, -10)
            for root in roots:
                G.add_edge(moduleName, root)

    fields = [("Req-Id", "@index")]
    posG = G.copy()
    for node_data in posG.nodes.values():
        for key in list(node_data.keys()):
            # Get all fields from all nodes to generate the tooltip
            if not "Req-Id" in key:
                fields.append(("\"" + key + "\"" , "\"@" + key + "\""))
            # Pop all all but description and color when generating the position
            if key not in ['Description', 'color']:
                node_data.pop(key)

        # Get color info for the nodes
        if 'color' in node_data.keys() and node_data['color'] in color_mapper.keys():
            colors.append(color_mapper[node_data['color']])
        else:
            colors.append(color_mapper['gray'])
    # Get the unique list
    fields = list(set(fields))
    print(fields)
    node_hover_tool = HoverTool(tooltips=fields)

    pos = graphviz_layout(posG, prog='dot')
    for spn, spp in special_pos.items():
        pos[spn] = (pos[spn][0]+spp[0], pos[spn][1]+spp[1])
    x, y = zip(*pos.values())
    plot = figure(title="Requirement connection visualization", x_range=(min(x)-10, max(x)+10), y_range=(min(y)-10, max(y)+10),
                  tools="tap", width=1700, height=800)

    plot.add_tools(node_hover_tool, BoxZoomTool(), ResetTool())

    graph_renderer = from_networkx(G, nx.spring_layout, pos=pos, k=3, center=(0, 0))
    graph_renderer.node_renderer.data_source.data['colors'] = colors
    graph_renderer.layout_provider = StaticLayoutProvider(graph_layout=pos)
    graph_renderer.node_renderer.glyph = Circle(size=50, fill_color='colors')
    #graph_renderer.node_renderer.glyph = Text(text=["@index"])
    graph_renderer.node_renderer.selection_glyph = Circle(size=50, fill_color=Spectral4[2])
    graph_renderer.node_renderer.hover_glyph = Circle(size=50, fill_color=Spectral4[1])

    graph_renderer.edge_renderer.glyph = MultiLine(line_color="#CCCCCC", line_alpha=0.8, line_width=5)
    graph_renderer.edge_renderer.selection_glyph = MultiLine(line_color=Spectral4[2], line_width=5)
    graph_renderer.edge_renderer.hover_glyph = MultiLine(line_color=Spectral4[1], line_width=5)

    #graph_renderer.selection_policy = NodesAndLinkedEdges()
    #graph_renderer.inspection_policy = EdgesAndLinkedNodes()

    plot.renderers.append(graph_renderer)



    node_labels = list(G.nodes.keys())
    source = ColumnDataSource({'x': x, 'y': y,
                               'Req-Id': [node_labels[i] for i in range(len(x))]})
    labels = LabelSet(x='x', y='y', text='Req-Id', source=source)

    plot.renderers.append(labels)

    output_file(reqmodule.module_path + "/" + reqmodule.module_prefix + "_networkx_graph.html")
    show(plot)
