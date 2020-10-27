import xlrd
import os
import yaml

def import_from_xls(reqmodule, req_xls):
    wb = xlrd.open_workbook(req_xls)
    sheet = wb.sheet_by_index(0)

    reqmodule.clear_ordered_req_list()

    fields = [field for field in sheet.row_values(0)]
    req = {}
    for row in range(1, sheet.nrows):
        for col, field in enumerate(fields):
            req[field] = sheet.cell_value(row, col)
        reqmodule.add_req(req)


def import_from_markdown(reqmodule, req_md):
    req = {}
    record_req = False
    with open(req_md, 'r') as md_file:
        md_line = md_file.readline()
        while md_line:
            if md_line[0:6] == '<!--- ' and md_line[6:13] == 'gitreq:':
                if md_line[13:19] == 'start:':
                    req = {}
                    req['Req-Id'] = md_line[19:].replace('-->\n', '')
                    req['Description'] = ""
                    record_req = True
                elif md_line[13:18] == 'stop:':
                    req['Description'] = req['Description'].replace(
                        '[' + req['Req-Id'] + ']', '').rstrip()
                    reqmodule.add_req(req)
                    record_req = False
            elif record_req:
                req['Description'] = req['Description'] + md_line
            md_line = md_file.readline()


def add_test_results(module_path, test_results_file):
    if os.path.exists(module_path + '/test_results.temp.yaml'):
        with open(module_path + '/test_results.temp.yaml', 'r') as testlist_file:
            test_result_files = yaml.safe_load(testlist_file)
            test_result_files.append(test_results_file)
    else:
        test_result_files = [test_results_file]

    with open(module_path + '/test_results.temp.json', 'w') as testlist_file:
        yaml.dump(test_result_files, testlist_file)
