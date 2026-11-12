import importlib.util
import json
import pathlib
import sys
import unittest

SCRIPT=pathlib.Path(__file__).resolve().parents[1]/"czech800_tool.py"
spec=importlib.util.spec_from_file_location("czech800_tool",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Czech800Tests(unittest.TestCase):
    def test_czech_normalization(self):
        self.assertEqual(m.normalize("  Závěr zápasu,   ALE!  "),"zaver zapasu ale")
        self.assertEqual(m.flat_word("na-děj-ný"),"nadejny")

    def test_classification(self):
        target={"czech_original":"nadějný","czech_corrected":"nadějný",
                "czech_sentence_original":"Závěr zápasu byl nadějný, ale nakonec jsme prohráli",
                "czech_sentence_corrected":"Závěr zápasu byl nadějný, ale nakonec jsme prohráli."}
        self.assertEqual(m.classify("nadějný",target)[0],"czech_word")
        self.assertEqual(m.classify("Závěr zápasu byl nadějný, ale nakonec jsme prohráli.",target)[0],"czech_sentence")
        self.assertEqual(m.classify("The cat sleeps at home",target)[0],"unclassified")

    def test_no_automatic_verification(self):
        source=SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"verified":False',source)
        self.assertIn('ASR_ESTIMATE_NOT_VERIFIED',source)
        self.assertIn("redistribution_rights",source)

if __name__=="__main__":
    unittest.main()
