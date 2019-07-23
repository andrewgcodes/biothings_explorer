from collections import defaultdict
from .utils import find_common_path, get_dict_values

from jsonpath_rw import jsonpath, parse

class Transformer():
    def __init__(self, json_doc, mapping):
        self.json_doc = json_doc
        self.mapping = mapping

    @staticmethod
    def generate_parser(path):
        """create path for jsonpath_rw
        example: ensembl.gene -> ensembl[*].gene[*]
        """
        return parse(('.').join([(_item + '[*]') for _item in path.split('.')]))

    @staticmethod
    def fetch_all_paths_from_dict(python_dict):
        paths = []
        for k, v in python_dict.items():
            if k != "@type":
                if type(v) == list:
                    paths += v
                else:
                    paths.append(v)
        return paths

    @staticmethod
    def group_jsonpaths(commonprefix, jsonpath_dict):
        result = defaultdict(list)
        # find the last common element, e.g. if 'go.BP' is common prefix, then 'BP' is the last common element
        lst_common_elem = commonprefix.rpartition('.')[2]
        for k, v in jsonpath_dict.items():
            assert type(v) == list
            for _path in v:
                splitted_path = _path.split('.')
                lst_common_element_idx = splitted_path.index(lst_common_elem)
                result['.'.join(splitted_path[0:lst_common_element_idx + 2])].append((k, _path))
        return dict(result)

    @staticmethod
    def fetch_value_by_jsonpath(json_dict, jsonpath):
        path_elements = jsonpath.split('.')
        result = json_dict
        for _ele in path_elements:
            if not _ele.startswith('['):
                result = result[_ele]
            else:
                if type(result) == list:
                    result = result[_ele]
                else:
                    result = result
        return result

    @staticmethod
    def find_key_by_value(json_dict, value):
        for k, v in json_dict.items():
            if type(v) == list:
                if value in v:
                    return k
            else:
                if v == value:
                    return k

    def parse_dict(self, mapping_dict):
        """
        mapping: {"bts:dd": "a.b.c", "bts:ee": "a.b.d"}
        case 1: {"a": {"b": {"c": 1, "d": 2}}}
        result 1: {"bts:dd": 1, "bts:ee": 2}
        case 2: {"a": [{"b": {"c": 1, "d": 2}}, {"b": {"c": 3, "d": 4}}]}
        result 2: [{"bts:dd": 1, "bts:ee": 2}]
        case 3: {"a": }
        """
        dict_values = get_dict_values(mapping_dict)
        common_path = find_common_path(dict_values)
        if common_path:
            all_paths = self.fetch_all_paths_from_dict(mapping_dict)
            paths_jsonpaths_dict = {}
            jsonpaths_values_dict = {}
            for path in all_paths:
                parser = self.generate_parser(path)
                parsing_result = parser.find(self.json_doc)
                jsonpaths = [str(match.full_path) for match in parsing_result]
                values = [match.value for match in parsing_result]
                jsonpaths_values_dict.update(dict(zip(jsonpaths, values)))
                paths_jsonpaths_dict.update({path: jsonpaths})
            grouped_jsonpaths = self.group_jsonpaths(common_path,
                                                     paths_jsonpaths_dict)
            result = []
            for v in grouped_jsonpaths.values():
                _result = defaultdict(list)
                for _tuple in v:
                    schema_prop = self.find_key_by_value(mapping_dict,
                                                         _tuple[0])
                    _result[schema_prop].append(jsonpaths_values_dict[_tuple[1]])
                result.append(dict(_result))
            return result
        else:
            result = {}
            for k,v in mapping_dict.items():
                if k != "@type":
                    if type(v) == str:
                        parser = self.generate_parser(v)
                        result[k] = self.fetch_value_from_single_path(parser)
                    elif type(v) == list:
                        _res = []
                        for path in v:
                            parser = self.generate_parser(path)
                            _res += self.fetch_value_from_single_path(parser)
                        result[k] = _res
            return result

    def fetch_value_from_single_path(self, parser):
        return [match.value for match in parser.find(self.json_doc)]

    def fetch_value(self, key, paths):
        if key in ["@context", "@type"]:
            return paths
        if type(paths) == str:
            parser = self.generate_parser(paths)
            return self.fetch_value_from_single_path(parser)
        elif type(paths) == list:
            result = []
            for path in paths:
                if type(path) == dict:
                    result += self.parse_dict(path)
                elif type(path) == str:
                    parser = self.generate_parser(path)
                    result += self.fetch_value_from_single_path(parser)
                else:
                    raise ValueError('{} is not valid'.format(path))
            return result
        elif type(paths) == dict:
            result = self.parse_dict(paths)
            return result
        else:
            return None

    def transform(self):
        new_json_doc = {k: self.fetch_value(k, v) for k,v in self.mapping.items()}
        return new_json_doc