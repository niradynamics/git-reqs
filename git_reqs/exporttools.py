import os.path
import xlwt
import networkx as nx
from networkx.drawing.nx_pydot import to_pydot, graphviz_layout

from bokeh.models import (BoxZoomTool, ResetTool, Circle, HoverTool,
                          MultiLine, StaticLayoutProvider, ColumnDataSource)
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn, Div
from bokeh.io import output_file, show, save, curdoc
from bokeh.layouts import column
from bokeh.palettes import Spectral4, RdGy6, Pastel2
from bokeh.plotting import figure, from_networkx
from bokeh.models import ColumnDataSource, LabelSet
import math

def convert_to_xls(reqmodule, file):
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('Reqs')

    for i, field in enumerate(reqmodule.fields):
        for k, req in enumerate(reqmodule.ordered_req_names):
            if field == "Req-Id":
                sheet.write(k+1, i, req)
            elif field in reqmodule.reqs.nodes[req].keys():
                sheet.write(k+1, i, reqmodule.reqs.nodes[req][field])

        sheet.write(0, i, field)
    workbook.save(file)


def convert_to_markdown(reqmodule, file, hugo=False):
    md_file = open(file)
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


def create_report(project, reqmodule_name, dont_show_output=False):

    graphs = column()
    if reqmodule_name:
        reqmodule = project.modules[reqmodule_name]
    else:
        reqmodule = project

    output_file(reqmodule.module_path + "/" + reqmodule.module_prefix + "_relations_report.html")

    for req in reqmodule.ordered_req_names:
        tree = get_tree_graph(reqmodule, req)
        subgraph, _, _ = reqmodule.get_related_reqs(req, reqmodule.reqs)
        table = get_table_of_subgraph_reqs(subgraph, reqmodule.fields)
        graphs.children.append(tree)
        graphs.children.append(table)
    if dont_show_output:
        save(graphs)
    else:
        show(graphs)

def get_empty_struct():
    req_group_fields = ['Req-Ids', 'result', 'leaves', 'fully-tested', 'Description']
    return {k: [] for k in req_group_fields}

def get_test_result(reqs, reqmodule, req_graph, passed_reqs, failed_reqs, fully_tested_reqs):
    result = get_empty_struct()
    for req in reqs['Req-Ids']:
        subgraph, ancestors, descendants = reqmodule.get_related_reqs(req, req_graph)
        leaves = [v for v, d in subgraph.out_degree() if d == 0]
        passed = 0
        failed = 0


        for leaf in leaves:
            if 'Type' in subgraph.nodes[leaf].keys() and subgraph.nodes[leaf]['Type'] == 'Test-Result':
                if subgraph.nodes[leaf]['result'] == 'Passed':
                    passed += 1
                else:
                    failed += 1
        if passed == len(leaves) and fully_tested_reqs:
            passed_reqs['Req-Ids'].append(req)
            passed_reqs['leaves'].append(leaves)
            passed_reqs['result'].append('passed')
            passed_reqs['fully-tested'].append(True)
            passed_reqs['Description'].append(reqmodule.reqs.nodes[req]['Description'])

        elif failed > 0:
            failed_reqs['Req-Ids'].append(req)
            failed_reqs['leaves'].append(leaves)
            failed_reqs['result'].append('failed')
            failed_reqs['fully-tested'].append(fully_tested_reqs)
            failed_reqs['Description'].append(reqmodule.reqs.nodes[req]['Description'])
        else:
            result['Req-Ids'].append(req)
            result['leaves'].append(leaves)
            result['result'].append('failed' if failed > 0 else ('partly tested' if passed > 0 else 'untested'))
            result['fully-tested'].append(fully_tested_reqs)
            result['Description'].append(reqmodule.reqs.nodes[req]['Description'])

    return result

def draw_coverage_diagrams(reqmodule, dont_show_output=False):
    only_reqs_subgraph = reqmodule.get_reqs_with_attr(('Type', 'Requirement'))
    reqs_test_testresult_subgraph = reqmodule.get_reqs_with_attr([('Type', 'Requirement'), ('Type', 'Testcase'), ('Type', 'Test-Result')])
    total_reqs = len(only_reqs_subgraph.nodes)

    req_group_fields = ['Req-Ids', 'result', 'leaves', 'fully-tested', 'Description']

    passed_reqs = get_empty_struct()
    failed_reqs = get_empty_struct()
    partly_tested_reqs = get_empty_struct()
    fully_tested_reqs = get_empty_struct()
    untested_reqs = get_empty_struct()

    partly_tested_reqs['Req-Ids'] = [n for n, r in only_reqs_subgraph.nodes.items()
                   if 'non_stored_fields' in r.keys()
                    and 'verifies_link_status' in r['non_stored_fields'].keys()
                    and 0 < r['non_stored_fields']['verifies_link_status'] < 1]
    fully_tested_reqs['Req-Ids'] = [n for n, r in only_reqs_subgraph.nodes.items()
                   if 'non_stored_fields' in r.keys()
                    and 'verifies_link_status' in r['non_stored_fields'].keys()
                    and r['non_stored_fields']['verifies_link_status'] >= 1]
    untested_reqs['Req-Ids'] = [n for n, r in only_reqs_subgraph.nodes.items()
                   if n not in partly_tested_reqs['Req-Ids'] and n not in fully_tested_reqs['Req-Ids']]

    partly_tested_reqs = get_test_result(partly_tested_reqs, reqmodule, reqs_test_testresult_subgraph, passed_reqs, failed_reqs, False)
    fully_tested_reqs = get_test_result(fully_tested_reqs, reqmodule, reqs_test_testresult_subgraph, passed_reqs, failed_reqs, True)
    untested_reqs = get_test_result(untested_reqs, reqmodule, reqs_test_testresult_subgraph, passed_reqs, failed_reqs, False)

    # file to save the model
    output_file(reqmodule.module_path + "/" + reqmodule.module_prefix + "_TestCoverage.html")

    # instantiating the figure object
    graph = figure(title="Test Coverage")
    graph.title.align = "center"
    graph.title.text_font_size = "25px"

    # name of the sectors
    sectors = ["Passed", "Failed", "Linked to full test coverage", "Partly tested", "Untested"]

    # % tage weightage of the sectors
    parts = [len(passed_reqs['Req-Ids'])/total_reqs,
             len(failed_reqs['Req-Ids'])/total_reqs,
             len(fully_tested_reqs['Req-Ids'])/total_reqs,
             len(partly_tested_reqs['Req-Ids'])/total_reqs,
             len(untested_reqs['Req-Ids'])/total_reqs]

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


    columns = [
        TableColumn(field="Req-Ids", title="Req-Id"),
        TableColumn(field="Description", title="Description"),
        TableColumn(field="result", title="Test Result"),
        TableColumn(field="leaves", title="Leaf nodes in traceability tree"),
    ]

    source = ColumnDataSource(failed_reqs)
    data_table1_div = Div(text="<b>Failed Requirements", style={'font-size': '200%', 'color': color[1]})
    data_table1 = DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600, height=len(failed_reqs['Req-Ids'])*35+35)

    source = ColumnDataSource(untested_reqs)
    data_table2_div = Div(text="<b>Untested Requirements", style={'font-size': '200%', 'color': color[4]})
    data_table2 = DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600, height=len(untested_reqs['Req-Ids'])*35+35)

    source = ColumnDataSource(partly_tested_reqs)
    data_table3_div = Div(text="<b>Partly tested Requirements", style={'font-size': '200%', 'color': color[3]})
    data_table3 = DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600, height=len(partly_tested_reqs['Req-Ids'])*35+35)

    source = ColumnDataSource(fully_tested_reqs)
    data_table4_div = Div(text="<b>Requirements fully linked to test</b>", style={'font-size': '200%', 'color': color[2]})
    data_table4 = DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600, height=len(fully_tested_reqs['Req-Ids'])*35+35)

    source = ColumnDataSource(passed_reqs)
    data_table5_div = Div(text="<b>Passed Requirements", style={'font-size': '200%', 'color': color[0]})
    data_table5 = DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600, height=len(passed_reqs['Req-Ids'])*35+35)

    graphs=(column(graph, data_table1_div, data_table1, data_table2_div, data_table2, data_table3_div, data_table3, data_table4_div, data_table4, data_table5_div, data_table5))

    if dont_show_output:
        save(graphs)
    else:
        show(graphs)

def get_table_of_subgraph_reqs(subgraph, fields):
    table = {k: [] for k in fields}
    columns = []
    for c in fields:
        for req in subgraph:
            if c in subgraph.nodes[req].keys():
                table[c].append(subgraph.nodes[req][c])
            else:
                table[c].append('')

        columns.append(TableColumn(field=c, title=c))

    source = ColumnDataSource(table)

    return DataTable(source=source, columns=columns, autosize_mode='fit_columns', width=1600,
                            height=len(table['Req-Id']) * 35 + 35)

def get_tree_graph(reqmodule, req):
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
            G.add_node(moduleName, non_stored_fields={'color': 'gray', 'link_status_updated': True})
            # Put the spec name node a bit lower to make the graph nicer
            special_pos[moduleName] = (0, -10)
            for root in roots:
                G.add_edge(moduleName, root)

    fields = [("Req-Id", "@index")]
    drawG = G.copy()
    posG = G.copy()
    for node, node_data in posG.nodes.items():
        for key in list(node_data.keys()):
            # Get all fields from all nodes to generate the tooltip
            if not "Req-Id" in key and not isinstance(node_data[key], dict):
                fields.append(("\"" + key + "\"", "\"@" + key + "\""))
            elif isinstance(node_data[key], dict):
                for sub_key in node_data[key].keys():
                    drawG.nodes[node][sub_key] = str(node_data[key][sub_key])
                    fields.append(("\"" + sub_key + "\"", "\"@" + sub_key + "\""))

            # Pop all all but description and color when generating the position
            if key not in ['Description', 'color']:
                node_data.pop(key)

        # Get color info for the nodes
        if req and node is req:
            colors.append(Spectral4[2])
        elif 'color' in node_data.keys() and node_data['color'] in color_mapper.keys():
            colors.append(color_mapper[node_data['color']])
        else:
            colors.append(color_mapper['gray'])
    # Get the unique list
    fields = list(set(fields))
    print(fields)


    pos = graphviz_layout(posG, prog='dot')
    for spn, spp in special_pos.items():
        pos[spn] = (pos[spn][0] + spp[0], pos[spn][1] + spp[1])
    x, y = zip(*pos.values())


    node_hover_tool = HoverTool(tooltips=fields)
    w = int(max(x)-min(x)) + 200
    h = int(max(y)-min(y)) + 200
    plot = figure(title="Requirement connection visualization", x_range=(min(x) - 50, max(x) + 50),
                  y_range=(min(y) - 50, max(y) + 50),
                  tools="tap", width=w, height=h)

    plot.add_tools(node_hover_tool, BoxZoomTool(), ResetTool())

    graph_renderer = from_networkx(drawG, nx.spring_layout, pos=pos, k=3, center=(0, 0))
    graph_renderer.node_renderer.data_source.data['colors'] = colors
    graph_renderer.layout_provider = StaticLayoutProvider(graph_layout=pos)
    graph_renderer.node_renderer.glyph = Circle(size=50, fill_color='colors')
    graph_renderer.node_renderer.selection_glyph = Circle(size=50, fill_color=Spectral4[2])
    graph_renderer.node_renderer.hover_glyph = Circle(size=50, fill_color=Spectral4[1])

    graph_renderer.edge_renderer.glyph = MultiLine(line_color="#CCCCCC", line_alpha=0.8, line_width=5)
    graph_renderer.edge_renderer.selection_glyph = MultiLine(line_color=Spectral4[2], line_width=5)
    graph_renderer.edge_renderer.hover_glyph = MultiLine(line_color=Spectral4[1], line_width=5)

    plot.renderers.append(graph_renderer)

    node_labels = list(drawG.nodes.keys())
    source = ColumnDataSource({'x': x, 'y': y,
                               'Req-Id': [node_labels[i] for i in range(len(x))]})
    labels = LabelSet(x='x', y='y', text='Req-Id', source=source)

    plot.renderers.append(labels)

    return plot

def draw_bokeh(reqmodule, req=None):
    plot = get_tree_graph(reqmodule, req)
    output_file(reqmodule.module_path + "/" + reqmodule.module_prefix + "_networkx_graph.html")
    show(plot)
