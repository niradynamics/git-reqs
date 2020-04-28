import os
import sys
import yaml
import networkx as nx
import junitparser
from junitparser import JUnitXml


class requirement_module:
    def __init__(self, module_path, parent_prefix=""):
        self.parent_prefix = parent_prefix
        self.module_path = module_path

        with open(module_path + '/next-id.yaml', 'r') as next_id_file:
            self.next_id = yaml.load(next_id_file)

        with open(module_path + '/module-prefix.yaml', 'r') as proj_pref_file:
            if parent_prefix != "":
                self.module_prefix = parent_prefix + \
                    '_' + yaml.load(proj_pref_file)
            else:
                self.module_prefix = yaml.load(proj_pref_file)

        self.reqs = nx.DiGraph()
        self.fields, self.ordered_req_names = self.read_reqs()

        self.modules = {}
        with open(module_path + '/modules.yaml', 'r') as modules_file:
            module_names = yaml.load(modules_file)

        for module in module_names:
            self.modules[module] = requirement_module(
                module_path + '/' + module, parent_prefix=self.module_prefix)
            self.reqs = nx.compose(self.reqs, self.modules[module].reqs)
            self.ordered_req_names.extend(
                self.modules[module].ordered_req_names)

        if os.path.exists(module_path + '/test_results.temp.yaml'):
            with open(module_path + '/test_results.temp.yaml', 'r') as test_results_file:
                test_result_files = yaml.load(test_results_file)
                for test_file in test_result_files:
                    self.import_test_results(test_file)

    def init_module(parent_path, module_name, module_prefix):
        module_path = parent_path + '/' + module_name
        assert(not os.path.exists(module_path + '/next-id.yaml'))
        assert(not os.path.exists(module_path + '/module-prefix.yaml'))
        assert(not os.path.exists(module_path + '/modules.yaml'))
        assert(not os.path.exists(module_path + '/reqs.yaml'))
        if not os.path.exists(module_path):
            os.mkdir(module_path)
        next_id = 1
        modules = []
        reqs = ""
        with open(module_path + '/next-id.yaml', 'w') as next_id_file:
            yaml.dump(next_id, next_id_file)
        with open(module_path + '/module-prefix.yaml', 'w') as proj_pref_file:
            yaml.dump(module_prefix, proj_pref_file)
        with open(module_path + '/modules.yaml', 'w') as modules_file:
            yaml.dump(modules, modules_file)
        with open(module_path + '/reqs.yaml', 'w') as reqs_file:
            yaml.dump(modules, reqs_file)

        if os.path.exists(parent_path + '/modules.yaml'):
            print(parent_path + '/modules.yaml')
            with open(parent_path + '/modules.yaml', 'r') as parent_modules_file:
                module_names = yaml.load(parent_modules_file)
                module_names.append(module_name)
                print(module_names)
            with open(parent_path + '/modules.yaml', 'w') as parent_modules_file:
                yaml.dump(module_names, parent_modules_file)

    def clear_ordered_req_list(self):
        self.ordered_req_names = []

    def add_req(self, req):
        if req['Req-Id'] == "":
            id = str(self.next_id)
            self.next_id += 1
            req['Req-Id'] = self.module_prefix + '_' + id
            self.reqs.add_node(req['Req-Id'])

        else:
            id = req['Req-Id'].split('_')[-1]
            assert(id.isdigit())
            assert(self.module_prefix in req['Req-Id'])

        self.reqs.nodes[self.module_prefix + '_' + id]['Req-Id'] = id
        for field in list(req.keys())[1:]:
            self.reqs.nodes[self.module_prefix + '_' + id][field] = req[field]

        self.ordered_req_names.append(req['Req-Id'])

    def write_reqs(self):
        for req_name in self.ordered_req_names:
            id = req_name.split('_')[-1]
            with open(self.module_path + '/' + id + '.yaml', 'w') as req_file:
                yaml.dump(self.reqs.nodes[req_name], req_file)

        with open(self.module_path + '/reqs.yaml', 'w') as doc_file:
            yaml.dump([req.split('_')[-1]
                       for req in self.ordered_req_names], doc_file)

        with open(self.module_path + '/next-id.yaml', 'w') as next_id_file:
            yaml.dump(self.next_id, next_id_file)

    def import_test_results(self, test_result_file):
        test_results = JUnitXml.fromfile(test_result_file)
        if isinstance(test_results, junitparser.junitparser.TestSuite):
            test_results = [test_results]

        for suite in test_results:
            for case in suite:
                if case.result is None:
                    result = 'Passed'
                    color = 'green'
                else:
                    result = case.result.tostring()
                    color = 'red'

                # Ok for nx to add node that already exists
                self.reqs.add_node(case.name, result=result,
                                   color=color, Type='Test-Result')

    def get_related_reqs(self, req_name):
        ancestors = nx.ancestors(self.reqs, req_name)
        descendants = nx.descendants(self.reqs, req_name)
        return nx.subgraph(self.reqs, ancestors | descendants | {req_name}), ancestors, descendants

    def read_reqs(self):
        with open(self.module_path + '/reqs.yaml', 'r') as req_list_file:
            req_list = yaml.load(req_list_file)

        fields = ['Req-Id', 'Type', 'Description',
                  'downward_links', 'upward_links']
        ordered_req_names = []
        for req_id in req_list:
            with open(self.module_path + '/' + req_id + '.yaml', 'r') as r:
                req = yaml.load(r)
            # Add prefixes recursivly
            req_name = self.module_prefix + '_' + req_id

            # Create graph node for each req
            self.reqs.add_node(req_name)
            self.reqs.nodes[req_name]['Internal'] = True
            self.reqs.nodes[req_name]['color'] = 'black'
            for field in req.keys():

                # Create links between linked nodes
                if "links" in field:
                    links = req[field].split(',')
                    for link in links:
                        if ':' in link:
                            link_type, linked_req = link.split(':')
                            # Don't add project prefix to extern links
                            if 'extern' not in link_type:
                                linked_req = self.parent_prefix + '_' + linked_req

                            # Ok for nx to add node that already exists
                            self.reqs.add_node(linked_req)
                            if self.module_prefix in linked_req:
                                self.reqs.nodes[linked_req]['Internal'] = True
                                self.reqs.nodes[linked_req]['color'] = 'black'
                            else:
                                self.reqs.nodes[linked_req]['color'] = 'gray'

                            # Verify that the requirement is not linked two ways.
                            uptest = (linked_req, req_name) in self.reqs.edges.keys(
                            ) and self.reqs.edges[(linked_req, req_name)]['type'] == link_type
                            downtest = (req_name, linked_req) in self.reqs.edges.keys(
                            ) and self.reqs.edges[(req_name, linked_req)]['type'] == link_type
                            assert(not (uptest and downtest))

                            if "upward" in field:
                                self.reqs.add_edge(
                                    linked_req, req_name, type=link_type)
                            else:
                                self.reqs.add_edge(
                                    req_name, linked_req, type=link_type)

                if not field in fields:
                    fields.append(field)

                # Add fields to node
                self.reqs.nodes[req_name][field] = req[field]

            if not req_name in ordered_req_names:
                ordered_req_names.append(req_name)

        return fields, ordered_req_names
