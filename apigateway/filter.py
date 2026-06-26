import re
from .models import SensitiveWord


class SensitiveFilter:
    def __init__(self):
        self._words = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        for w in SensitiveWord.objects.filter(enabled=True):
            self._words[w.word] = {'level': w.level, 'replacement': w.replacement}
        self._loaded = True

    def reload(self):
        self._words = {}
        self._loaded = False
        self._load()

    def check(self, text):
        if not text:
            return [], text, False
        self._load()
        hits = []
        cleaned = str(text)
        blocked = False

        for word, config in self._words.items():
            if word in cleaned:
                hits.append(word)
                if config['level'] == 'block':
                    blocked = True
                elif config['level'] == 'replace':
                    cleaned = cleaned.replace(word, config['replacement'])

        return hits, cleaned, blocked

    def filter_body(self, data):
        if isinstance(data, str):
            result, hits = self._filter_string(data, 'input')
            return result, hits
        if isinstance(data, dict):
            return self._filter_dict(data)
        if isinstance(data, list):
            results = []
            all_hits = []
            for item in data:
                result, hits = self.filter_body(item)
                results.append(result)
                all_hits.extend(hits)
            return results, all_hits
        return data, []

    def _filter_dict(self, d):
        hits = []
        result = {}
        for k, v in d.items():
            if isinstance(v, str):
                h, cleaned, blocked = self.check(v)
                hits.extend(h)
                result[k] = cleaned
            elif isinstance(v, (dict, list)):
                filtered, h = self.filter_body(v)
                hits.extend(h)
                result[k] = filtered
            else:
                result[k] = v
        return result, hits

    def _filter_string(self, text, direction):
        h, cleaned, blocked = self.check(text)
        return cleaned, h


filter_instance = SensitiveFilter()
