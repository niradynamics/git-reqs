import unittest
import sys
import os
import yaml
sys.path.append("../git_reqs")
import requirementmodule

def strip(reqmodule):
    for req in reqmodule.reqs:
        reqmodule.reqs.nodes[req].pop('non_stored_fields')
    return reqmodule

class TestRequirementModule(unittest.TestCase):

    def test_read_reqs(self):
        # Create some reqs
        Req_1 = {'Req-Id': 'Req_1', 'Type': 'Requirement', 'Description': 'Req desc 1',
                 'upward_links': 'extern:Ext_1'}
        Req_2 = {'Req-Id': 'Req_2', 'Type': 'Requirement', 'Description': 'Req desc 2',
                 'downward_links': 'verifies:Test_1', 'upward_links': 'refines:Req_1'}
        Test_1 = {'Req-Id': 'Test_1', 'Type': 'Testcase', 'Description': 'Test desc 1'}
        reqs = {'_Req_1': Req_1, '_Req_2': Req_2, '_Test_1': Test_1}

        # Dump tp yaml
        module_path = os.getcwd() + '/test_read_reqs'
        if not os.path.exists(module_path):
            os.mkdir(module_path)

        for req in reqs.values():
            with open(module_path + '/' + req['Req-Id'] + '.yaml', 'w') as req_file:
                yaml.dump(req, req_file)

        with open(module_path + '/reqs.yaml', 'w') as reqs_file:
            yaml.dump([req['Req-Id'] for req in reqs.values()], reqs_file)

        # Read in the yaml files with git-reqs
        req_module = requirementmodule.requirement_module(module_path)

        # Check that the order of the reqs are correct (add module prefix to names):
        self.assertEqual(req_module.ordered_req_names, ['_' + req['Req-Id'] for req in reqs.values()])

        # Add the external node to the testset:
        reqs['Ext_1'] = {}

        # Check that all nodes contain the correct information:
        self.assertEqual(strip(req_module).reqs.nodes, reqs)

        # Check that the edges are connected correctly:
        expected_list = [('Ext_1', '_Req_1'), ('_Req_1', '_Req_2'), ('_Req_2', '_Test_1')]
        expected_list.sort()
        actual_list = [e for e in req_module.reqs.edges]
        actual_list.sort()
        self.assertListEqual(actual_list, expected_list)

        # Check that the edges has the correct values:
        expected_list = [('Ext_1', '_Req_1'), ('_Req_1', '_Req_2'), ('_Req_2', '_Test_1')]
        expected_values = [{'type': 'extern'}, {'type': 'refines'}, {'type': 'verifies'}]
        for v, n in zip(expected_values, expected_list):
            self.assertEqual(req_module.reqs.get_edge_data(n[0], n[1]), v)

    def test_write_reqs(self):
        # Create a temp folder
        module_path = os.getcwd() + '/test_write_reqs'
        if not os.path.exists(module_path):
            os.mkdir(module_path)

        # Create an empty git-reqs module:
        req_module = requirementmodule.requirement_module(module_path)


        # Create some reqs and add them to git-reqs, let git-reqs create req-ids
        Req_1 = {'Req-Id': '', 'Type': 'Requirement', 'Description': 'Req desc 1',
                 'upward_links': 'extern:Ext_1'}
        Req_1_name = req_module.add_req(Req_1)
        Req_1['Req-Id'] = Req_1_name.split('_')[-1]

        Test_1 = {'Req-Id': '', 'Type': 'Testcase', 'Description': 'Test desc 1'}
        Test_1_name = req_module.add_req(Test_1)
        Test_1['Req-Id'] = Test_1_name.split('_')[-1]

        Req_2 = {'Req-Id': '', 'Type': 'Requirement', 'Description': 'Req desc 2',
                 'downward_links': 'verifies:%s' % Test_1_name, 'upward_links': 'refines:%s' % Req_1_name}
        Req_2_name = req_module.add_req(Req_2)
        Req_2['Req-Id'] = Req_2_name.split('_')[-1]

        reqs = {Req_1_name: Req_1, Req_2_name: Req_2, Test_1_name: Test_1}

        # Write reqs
        req_module.write_reqs()

        # Read the yaml files:
        for req in reqs.values():
            with open(module_path + '/' + req['Req-Id'] + '.yaml', 'r') as req_file:
                read_req = yaml.safe_load(req_file)
                self.assertEqual(read_req, req)

    def test_update_link_status(self):
        req_module = requirementmodule.requirement_module()

        Test_1 = req_module.add_req({'Req-Id': ""})
        Test_2 = req_module.add_req({'Req-Id': ""})
        Test_3 = req_module.add_req({'Req-Id': ""})
        Impl_2 = req_module.add_req({'Req-Id': ""})
        Impl_3 = req_module.add_req({'Req-Id': ""})
        Req_1 = req_module.add_req({'Req-Id': ""})
        Req_2 = req_module.add_req({'Req-Id': ""})
        Req_3 = req_module.add_req({'Req-Id': ""})

        req_module.reqs.add_edge(Req_2, Test_1, type='partly_verifies(1/2)')
        req_module.reqs.add_edge(Req_2, Test_2, type='partly_verifies(1/2)')
        req_module.reqs.add_edge(Req_3, Test_3, type='partly_verifies(1/2)')

        req_module.reqs.add_edge(Req_1, Req_2, type='partly_refines(1/2)')
        req_module.reqs.add_edge(Req_1, Req_3, type='partly_refines(1/2)')

        req_module.reqs.add_edge(Req_2, Impl_2, type='implements')
        req_module.reqs.add_edge(Req_3, Impl_3, type='implements')

        for req in req_module.reqs:
            req_module.update_link_status(req)

        # Req 2 is partly verified(1/2) by two tests -> Verification status = 1
        # Req 2 is fully implemented by one item -> Implementation status = 1
        self.assertEqual(req_module.reqs.nodes[Req_2]['non_stored_fields']['verifies_link_status'], 1)
        self.assertEqual(req_module.reqs.nodes[Req_2]['non_stored_fields']['implements_link_status'], 1)

        # Req 3 is partly verified(1/2) by one test -> Verification status = 0.5
        # Req 3 is fully implemented by one item -> Implementation status = 1
        self.assertEqual(req_module.reqs.nodes[Req_3]['non_stored_fields']['verifies_link_status'], 0.5)
        self.assertEqual(req_module.reqs.nodes[Req_3]['non_stored_fields']['implements_link_status'], 1)

        # Req 1 is partly refined(1/2) by two requirements -> Refine status = 1
        # Req 1 is verified with it's descendants, fully (2/2) and partly (1/2) -> Verification status = (3/2)/2 = 3/4
        # Req 1 is fully implemented with it's descendants -> Implementation status = (1+1)/2=1
        self.assertEqual(req_module.reqs.nodes[Req_1]['non_stored_fields']['refines_link_status'], 1)
        self.assertEqual(req_module.reqs.nodes[Req_1]['non_stored_fields']['verifies_link_status'], 0.75)
        self.assertEqual(req_module.reqs.nodes[Req_1]['non_stored_fields']['implements_link_status'], 1)


if __name__ == '__main__':
    unittest.main()







