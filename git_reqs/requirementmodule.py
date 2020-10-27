import os
import yaml
import networkx as nx
import junitparser
from junitparser import JUnitXml
import git
import hashlib
import time
FORMAT_VERSION = 0.2

class requirement_module:
    def __init__(self, module_path, parent_prefix=""):
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
            with open(module_path + '/module-prefix.yaml', 'r') as proj_pref_file:
                self.config['module_prefix'] = yaml.safe_load(proj_pref_file)
            with open(module_path + '/modules.yaml', 'r') as modules_file:
                self.config['modules'] = yaml.safe_load(modules_file)
            self.config['req_number_format'] = 'numbers'
            self.used_ids = []

        else:
            with open(module_path + '/used-ids.yaml', 'r') as used_ids_file:
                self.used_ids = yaml.safe_load(used_ids_file)

        with open(module_path + '/next-id.yaml', 'r') as next_id_file:
            self.next_id = yaml.safe_load(next_id_file)

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
                module_path + '/' + module, parent_prefix=self.module_prefix)
            self.reqs = nx.compose(self.reqs, self.modules[module].reqs)

        if os.path.exists(module_path + '/test_results.temp.yaml'):
            with open(module_path + '/test_results.temp.yaml', 'r') as test_results_file:
                test_result_files = yaml.safe_load(test_results_file)
                for test_file in test_result_files:
                    self.import_test_results(test_file)

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

        self.reqs.nodes[self.module_prefix + '_' + id]['Req-Id'] = id
        for field in list(req.keys())[1:]:
            self.reqs.nodes[self.module_prefix + '_' + id][field] = str(req[field]).strip()
        if position >= 0:
            self.ordered_req_names.insert(position, req['Req-Id'])
        else:
            self.ordered_req_names.append(req['Req-Id'])

    def write_reqs(self):
        bare_ids = [req.split('_')[-1] for req in self.ordered_req_names]

        # Write requirement updates
        for id, req_name in zip(bare_ids, self.ordered_req_names):
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
            module.write_reqs()

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
            req_list = yaml.safe_load(req_list_file)

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
            self.reqs.nodes[req_name]['Internal'] = True
            self.reqs.nodes[req_name]['color'] = 'black'
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
        with open(module_path + '/../config.yaml', 'r') as parent_config_file:
            yaml.dump(config, parent_config_file)
        parent_git_repo = git.Repo(parent_path, search_parent_directories=True)
        parent_git_repo.git.add(module_path + '/../config.yaml')