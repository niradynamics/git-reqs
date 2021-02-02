import os
import yaml
import networkx as nx
import junitparser
from junitparser import JUnitXml
import git
import hashlib
import time
FORMAT_VERSION = 0.3
import re

class requirement_module:
    def __init__(self, module_path="", parent_prefix="", root_module=True):
        self.parent_prefix = parent_prefix
        self.module_path = module_path
        self.git_repo = git.Repo(self.module_path, search_parent_directories=True)

        if os.path.exists(module_path + '/config.yaml'):
            with open(module_path + '/config.yaml', 'r') as config_file:
                self.config = yaml.safe_load(config_file)
        else:
            self.config = {}
            self.config['req_version'] = 0.1


        if self.config['req_version'] < 0.2:
            if os.path.exists(module_path + '/config.yaml'):
                with open(module_path + '/module-prefix.yaml', 'r') as proj_pref_file:
                    self.config['module_prefix'] = yaml.safe_load(proj_pref_file)
            else:
                self.config['module_prefix'] = ""

            if os.path.exists(module_path + '/modules.yaml'):
                with open(module_path + '/modules.yaml', 'r') as modules_file:
                    self.config['modules'] = yaml.safe_load(modules_file)
            else:
                self.config['modules'] = []

            self.config['req_number_format'] = 'numbers'
            self.used_ids = []

        elif os.path.exists(module_path + '/used-ids.yaml'):
            with open(module_path + '/used-ids.yaml', 'r') as used_ids_file:
                self.used_ids = yaml.safe_load(used_ids_file)
        else:
            self.used_ids = []

        if os.path.exists(module_path + '/next-id.yaml'):
            with open(module_path + '/next-id.yaml', 'r') as next_id_file:
                self.next_id = yaml.safe_load(next_id_file)
        else:
            self.next_id = 0

        if parent_prefix != "":
            self.module_prefix = parent_prefix + \
                '_' + self.config['module_prefix']
        else:
            self.module_prefix = self.config['module_prefix']

        self.reqs = nx.DiGraph()
        self.fields, self.ordered_req_names = self.read_reqs()

        self.modules = {}
        for module in self.config['modules']:
            self.modules[module] = requirement_module(
                module_path + '/' + module, parent_prefix=self.module_prefix, root_module=False)
            self.reqs = nx.compose(self.reqs, self.modules[module].reqs)

        # Propagate the full graph upwards to all modules
        if root_module:
            self.update_to_root_graph(self.reqs)


        if os.path.exists(module_path + '/test_results.temp.yaml'):
            with open(module_path + '/test_results.temp.yaml', 'r') as test_results_file:
                test_result_files = yaml.safe_load(test_results_file)
                for test_file in test_result_files:
                    self.import_test_results(test_file)
        if root_module:
            for req in self.reqs:
                self.update_link_status(req)

    def read_reqs(self):
        if os.path.exists(self.module_path + '/reqs.yaml'):
            with open(self.module_path + '/reqs.yaml', 'r') as req_list_file:
                req_list = yaml.safe_load(req_list_file)
        else:
            req_list = []

        fields = ['Req-Id', 'Type', 'Description',
                  'downward_links', 'upward_links']
        ordered_req_names = []
        for req_id in req_list:
            with open(self.module_path + '/' + req_id + '.yaml', 'r') as r:
                req = yaml.safe_load(r)
            # Add prefixes recursivly
            req_name = self.module_prefix + '_' + req_id

            # Create graph node for each req
            self.reqs.add_node(req_name)
            for field in req.keys():

                # Create links between linked nodes
                if "links" in field:
                    links = req[field].split(',')
                    for link in links:
                        if ':' in link:
                            link_type, linked_req = link.split(':')
                            link_type = link_type.strip()
                            # Don't add project prefix to extern links
                            if 'extern' not in link_type:
                                linked_req = self.parent_prefix + '_' + linked_req.strip()

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
                            self.reqs.nodes[linked_req]['non_stored_fields'] = {}
                            self.reqs.nodes[linked_req]['non_stored_fields']['Internal'] = False
                            self.reqs.nodes[linked_req]['non_stored_fields']['color'] = 'gray'
                            self.reqs.nodes[linked_req]['non_stored_fields']['link_status_updated'] = False

                if not field in fields:
                    fields.append(field)

                # Add fields to node
                self.reqs.nodes[req_name][field] = req[field]

            self.reqs.nodes[req_name]['non_stored_fields'] = {}
            self.reqs.nodes[req_name]['non_stored_fields']['Internal'] = True
            self.reqs.nodes[req_name]['non_stored_fields']['color'] = 'black'
            self.reqs.nodes[req_name]['non_stored_fields']['link_status_updated'] = False
            if not req_name in ordered_req_names:
                ordered_req_names.append(req_name)

        return fields, ordered_req_names

    def update_link_status(self, req, subgraph=None):
        if not self.reqs.nodes[req]['non_stored_fields']['link_status_updated']:
            if subgraph is None:
                subgraph = self.reqs

            # Recurse down in the tree
            subgraph, _, descendants = self.get_related_reqs(req, subgraph)
            descendants_status = {}
            for descendant in descendants:
                self.update_link_status(descendant, subgraph)

                # Store the childrens status, so it can be propagated upwards
                desc_info = self.reqs.nodes[descendant]['non_stored_fields']
                desc_link_types = [key for key in desc_info if '_link_status' in key]

                for desc_link_type in desc_link_types:
                    if not desc_link_type in descendants_status.keys():
                        descendants_status[desc_link_type] = []

                    descendants_status[desc_link_type].append(desc_info[desc_link_type])

            # Check all outgoing links
            for descendant_link in self.reqs.out_edges(req):
                edge_data = self.reqs.get_edge_data(descendant_link[0], descendant_link[1])
                # Calculate the quota for partly links
                if 'partly_' in edge_data['type']:
                    link_type = edge_data['type'][len('partly_'):-5] + '_link_status'
                    quota = [float(n) for n in edge_data['type'][-4:-1].split('/')]
                    fulfillment = quota[0]/quota[1]
                else:
                    link_type = edge_data['type'] + '_link_status'
                    fulfillment = 1

                # Add link status for current req
                if not link_type in self.reqs.nodes[req]['non_stored_fields'].keys():
                    self.reqs.nodes[req]['non_stored_fields'][link_type] = 0
                self.reqs.nodes[req]['non_stored_fields'][link_type] += fulfillment

            # If the sub requirement is not fully fulfilled for a certain link type, inherit the min fulfillment.
            for link_type in descendants_status.keys():
                if len(descendants_status[link_type]) > 0:
                    sub_fullf = sum([f/len(descendants_status[link_type]) for f in descendants_status[link_type]])
                    if link_type in self.reqs.nodes[req]['non_stored_fields'].keys():
                        self.reqs.nodes[req]['non_stored_fields'][link_type] = min(self.reqs.nodes[req]['non_stored_fields'][link_type], sub_fullf)
                    else:
                        self.reqs.nodes[req]['non_stored_fields'][link_type] = sub_fullf

            self.reqs.nodes[req]['non_stored_fields']['link_status_updated'] = True

	
	# Propagates the reference of the full project graph to all modules
    # This is so that changes can be done on any level, and all requirements shall only exist once.
    def update_to_root_graph(self, root_reqs):
        self.reqs = root_reqs
        for module in self.config['modules']:
            self.modules[module].update_to_root_graph(root_reqs)

    def upgrade_module(self):
        self.config['req_version'] = FORMAT_VERSION
        with open(self.module_path + '/config.yaml', 'w') as config_file:
            yaml.dump(self.config, config_file)
        self.git_repo.git.add(self.module_path + '/config.yaml')
        self.write_reqs()

        if os.path.exists(self.module_path + '/module-prefix.yaml'):
            self.git_repo.git.rm(self.module_path + '/module-prefix.yaml')
        if os.path.exists(self.module_path + '/modules.yaml'):
            self.git_repo.git.rm(self.module_path + '/modules.yaml')

    def clear_ordered_req_list(self):
        self.ordered_req_names = []

    def add_req_with_path(self, module_path, req):
        # Add the req in the correct module
        submodule = self
        for module in module_path.split("/"):
            submodule = submodule.modules[module]

        name = submodule.add_req(req)
        # Remove project prefix
        return '_'.join(name.split('_')[1:])

    def add_req(self, req, position=-1):
        if req['Req-Id'] == "":
            if self.config['req_number_format'] == 'time_hash':
                hash = hashlib.sha1()
                while True:
                    hash.update(str(time.time()).encode('utf-8'))
                    id = hash.hexdigest()[:5]
                    if id not in self.used_ids:
                        break
            else:
                id = str(self.next_id)
                self.next_id += 1
            req['Req-Id'] = self.module_prefix + '_' + id
            self.reqs.add_node(req['Req-Id'])

        else:
            id = req['Req-Id'].split('_')[-1]
            if not self.config['req_number_format'] == 'time_hash':
                assert(id.isdigit())
            assert(self.module_prefix in req['Req-Id'])

        if id not in self.used_ids:
            self.used_ids.append(id)

        self.reqs.nodes[req['Req-Id']]['non_stored_fields'] = {}
        self.reqs.nodes[req['Req-Id']]['non_stored_fields']['Internal'] = True
        self.reqs.nodes[req['Req-Id']]['non_stored_fields']['color'] = 'black'
        self.reqs.nodes[req['Req-Id']]['non_stored_fields']['link_status_updated'] = False

        for field in list(req.keys()):
            self.reqs.nodes[req['Req-Id']][field] = str(req[field]).strip()
        self.reqs.nodes[req['Req-Id']]['Req-Id'] = id
        if position >= 0:
            self.ordered_req_names.insert(position, req['Req-Id'])
        else:
            self.ordered_req_names.append(req['Req-Id'])



        return req['Req-Id']

    def write_reqs(self):
        bare_ids = [req.split('_')[-1] for req in self.ordered_req_names]

        # Write requirement updates
        for id, req_name in zip(bare_ids, self.ordered_req_names):
            # pop fields we don't want to store in the files
            if 'non_stored_fields' in self.reqs.nodes[req_name].keys():
                self.reqs.nodes[req_name].pop('non_stored_fields')

            with open(self.module_path + '/' + id + '.yaml', 'w') as req_file:
                yaml.dump(self.reqs.nodes[req_name], req_file)
            self.git_repo.git.add(self.module_path + '/' + id + '.yaml')
            if not id in self.used_ids:
                self.used_ids.append(id)

        # Make sure all deleted reqs are set to deleted status
        for deleted_req in [r for r in self.used_ids if r not in bare_ids]:
            file_path = self.module_path + '/' + deleted_req + '.yaml'
            if os.path.exists(file_path):
                with open(file_path, 'r') as del_req_file:
                    del_req = yaml.safe_load(del_req_file)
                    del_req['Status'] = 'deleted'
                with open(file_path, 'w') as del_req_file:
                    yaml.dump(del_req, del_req_file)
                self.git_repo.git.add(file_path)


        # Write module files
        with open(self.module_path + '/reqs.yaml', 'w') as doc_file:
            yaml.dump([req.split('_')[-1]
                       for req in self.ordered_req_names], doc_file)

        if self.config['req_version'] >= 0.2:
            with open(self.module_path + '/used-ids.yaml', 'w') as used_ids_file:
                yaml.dump(self.used_ids, used_ids_file)
            self.git_repo.git.add(self.module_path + '/used-ids.yaml')

        with open(self.module_path + '/next-id.yaml', 'w') as next_id_file:
            yaml.dump(self.next_id, next_id_file)
            self.git_repo.git.add(self.module_path + '/reqs.yaml',
                                  self.module_path + '/next-id.yaml')

        for _, module in self.modules.items():
            # Copy the reqs from the parent module, since modifications can have been made here.
            #module.reqs = self.reqs.copy()
            #module.reqs.remove_nodes_from(n for n in self.reqs if n not in module.reqs)
            module.write_reqs()

    def get_link_regex(self):
        regex_pattern = "git-reqs: (\S*) (\S*) (\S*)"
        return re.compile(regex_pattern)

    def import_test_results(self, test_result_file, connect_with_naming_convention=True):
        pattern = self.get_link_regex()
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

                match = re.search(pattern, case.name)
                if match:
                    testname = '_'.join([self.module_prefix.split('_')[0],match.groups()[0]])
                    linktype = match.groups()[1]
                    # Ok for nx to add node that already exists
                    self.reqs.add_node(testname + '_result', result=result,
                                       non_stored_fields={'color': color, 'link_status_updated': True}, Type='Test-Result', Description=case.name)
                    self.reqs.add_edge(testname, testname + '_result', type='Test-Result')
                elif connect_with_naming_convention:
                    self.reqs.add_node(case.name + '_result', result=result,
                                   non_stored_fields={'color': color, 'link_status_updated': True}, Type='Test-Result')

                    for req_name, req_content in self.reqs.nodes.items():
                        if 'Description' in req_content.keys() and case.name in req_content['Description']:
                            self.reqs.add_edge(req_name, case.name)

    def get_related_reqs(self, req_name, subgraph=None):
        if subgraph:
            reqs = subgraph
        else:
            reqs = self.reqs
        ancestors = nx.ancestors(reqs, req_name)
        descendants = nx.descendants(reqs, req_name)
        return nx.subgraph(reqs, ancestors | descendants | {req_name}), ancestors, descendants

    def get_reqs_with_attr(self, fields):
        if not isinstance(fields, list):
            fields = [fields]
        nodes = []
        for field in fields:
            nodes.extend([n for n, d in self.reqs.nodes.items() if field[0] in d.keys() and d[field[0]] == field[1]])
        return self.reqs.subgraph(nodes)

def init_module(parent_path, module_name, module_prefix, req_numbering='time_hash'):
    module_path = parent_path + '/' + module_name
    if not os.path.exists(module_path):
        os.mkdir(module_path)
    assert(not module_name == '')
    assert(not os.path.exists(module_path + '/config.yaml'))
    assert(not os.path.exists(module_path + '/next-id.yaml'))
    assert(not os.path.exists(module_path + '/used-ids.yaml'))
    assert(not os.path.exists(module_path + '/reqs.yaml'))

    config = {}
    config['req_version'] = FORMAT_VERSION
    config['req_number_format'] = req_numbering
    config['module_prefix'] = module_prefix
    config['modules'] = []
    config['source_paths'] = []
    config['source_extensions'] = []
    next_id = 1

    with open(module_path + '/config.yaml', 'w') as config_file:
        yaml.dump(config, config_file)
    with open(module_path + '/next-id.yaml', 'w') as next_id_file:
        yaml.dump(next_id, next_id_file)
    with open(module_path + '/used-ids.yaml', 'w') as used_ids_file:
        yaml.dump([], used_ids_file)
    with open(module_path + '/modules.yaml', 'w') as modules_file:
        yaml.dump([], modules_file)
    with open(module_path + '/reqs.yaml', 'w') as reqs_file:
        yaml.dump([], reqs_file)

    if os.path.exists(module_path + '/../config.yaml'):
        with open(module_path + '/../config.yaml', 'r') as parent_config_file:
            config = yaml.safe_load(parent_config_file)
            config['modules'].append(module_name)
            print(config['modules'])
        with open(module_path + '/../config.yaml', 'w') as parent_config_file:
            yaml.dump(config, parent_config_file)
        parent_git_repo = git.Repo(parent_path, search_parent_directories=True)
        parent_git_repo.git.add(module_path + '/../config.yaml')