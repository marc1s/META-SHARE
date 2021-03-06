import sys

from difflib import unified_diff

from django.test import TestCase

from xml.etree.ElementTree import fromstring, tostring, register_namespace

from metashare import test_utils
from metashare.repository.models import resourceInfoType_model, \
    SCHEMA_NAMESPACE, lingualityInfoType_model
from metashare.repository.model_utils import get_root_resources
from metashare.settings import ROOT_PATH
from metashare.xml_utils import pretty_xml


class ModelTest(TestCase):
    """
    Tests the import/export properties of the generated object model.
    """
    def setUp(self):
        """
        Set up the email test
        """
        test_utils.setup_test_storage()
        _fixture = '{0}/repository/fixtures/testfixture.xml'.format(ROOT_PATH)
        _result = test_utils.import_xml(_fixture)
        self.resource_id = _result[0].id
    
    def tearDown(self):
        """
        Clean up the test
        """
        resourceInfoType_model.objects.all().delete()
    
    def testRollbackOnImportError(self):
        """
        Checks that a complete rollback is performed on import error.
        """
        _database = {}
        _models = [x for x in dir(sys.modules['metashare.repository.models'])
          if x.endswith('_model')]
        
        for _model in _models:
            if hasattr(sys.modules['metashare.repository.models'], _model):
                _inst = getattr(sys.modules['metashare.repository.models'], _model)
                _database[_model] = _inst.objects.count()
        
        _broken_fixture = '{0}/repository/fixtures/broken.xml'.format(ROOT_PATH)
        result = test_utils.import_xml(_broken_fixture)
        
        self.assertEqual(result[:2], (None, []))
        
        errors = []
        for _model in _models:
            if hasattr(sys.modules['metashare.repository.models'], _model):
                _inst = getattr(sys.modules['metashare.repository.models'], _model)
                print "Testing rollback for {}...".format(_model)
                if _database[_model] != _inst.objects.count():
                    errors.append(_model)
        
        self.assertEqual(errors, [])
    

    def assert_import_equals_export(self, _roundtrip):
        _result = test_utils.import_xml(_roundtrip)
        with open(_roundtrip) as _import_file:
            _import_xml = _import_file.read()
            register_namespace('', SCHEMA_NAMESPACE)
            _import_xml = tostring(fromstring(_import_xml))
        _export_xml = tostring(_result[0].export_to_elementtree())
    # cfedermann: uncomment these lines to dump import/export XML to file.
    #
    #with open('/tmp/_import.xml', 'w') as _out:
    #    _out.write(pretty_xml(_import_xml).encode('utf-8'))
    #with open('/tmp/_export.xml', 'w') as _out:
    #    _out.write(pretty_xml(_export_xml).encode('utf-8'))
        _pretty_import = pretty_xml(_import_xml).strip().encode('utf-8')
        _pretty_export = pretty_xml(_export_xml).strip().encode('utf-8')
        diff = '\n'.join(unified_diff(_pretty_import.split('\n'), _pretty_export.split('\n')))
        self.assertEqual(_pretty_import, _pretty_export,
             msg='For file {0}, export differs from import:\n{1}'.format(_roundtrip, diff))

    def testImportExportRoundtrip(self):
        """
        Checks that there is no data lost when exporting an imported XML.
        """
        _roundtrip = '{0}/repository/fixtures/roundtrip.xml'.format(ROOT_PATH)
        self.assert_import_equals_export(_roundtrip)

    def testImportExportRoundtrip0(self):
        """
        Checks that there is no data lost when exporting an imported XML.
        """
        _roundtrip = '{0}/repository/fixtures/ILSP10.xml'.format(ROOT_PATH)
        self.assert_import_equals_export(_roundtrip)

    def test_delete_deep(self):
        resource = resourceInfoType_model.objects.get(pk=self.resource_id)
        num_before = lingualityInfoType_model.objects.all().count()
        resource.delete_deep()
        num_after = lingualityInfoType_model.objects.all().count()
        self.assertEquals(num_before - 1, num_after)

    if False:
        def testImportExportRoundtrip1(self):
            """
            Checks that there is no data lost when exporting an imported XML.
            """
            _roundtrip = '{0}/repository/test_fixtures/ingested-corpus-AudioVideo-French.xml'.format(ROOT_PATH)
            self.assert_import_equals_export(_roundtrip)
    
        def testImportExportRoundtrip2(self):
            """
            Checks that there is no data lost when exporting an imported XML.
            """
            _roundtrip = '{0}/repository/test_fixtures/internal-lexConcept-Text-Eng.xml'.format(ROOT_PATH)
            self.assert_import_equals_export(_roundtrip)
    
        def testImportExportRoundtrip3(self):
            """
            Checks that there is no data lost when exporting an imported XML.
            """
            _roundtrip = '{0}/repository/fixtures/published-corpus-AudioVideo-English.xml'.format(ROOT_PATH)
            self.assert_import_equals_export(_roundtrip)
    
        def testImportExportRoundtrip4(self):
            """
            Checks that there is no data lost when exporting an imported XML.
            """
            _roundtrip = '{0}/repository/test_fixtures/published-lexConcept-Audio-EnglishGerman.xml'.format(ROOT_PATH)
            self.assert_import_equals_export(_roundtrip)


class ModelUtilsTest(TestCase):
    """
    Tests for model_utils.py.
    """
    def setUp(self):
        """
        Imports a few test resources.
        """
        self.test_res_1 = test_utils.import_xml(
            '{0}/repository/fixtures/testfixture.xml'.format(ROOT_PATH))[0]
        self.test_res_2 = test_utils.import_xml(
            '{0}/repository/fixtures/ILSP10.xml'.format(ROOT_PATH))[0]

    def tearDown(self):
        """
        Cleans the database after a test.
        """
        resourceInfoType_model.objects.all().delete()

    def test_get_root_resources(self):
        """
        Tests the `get_root_resources` method.
        """
        # test with no arguments
        self.assertSetEqual(set(), get_root_resources())
        # test with a resource argument
        self.assertSetEqual(set((self.test_res_1,)),
            get_root_resources(self.test_res_1))
        # test with nested model instance
        self.assertSetEqual(set((self.test_res_1,)),
            get_root_resources(self.test_res_1.identificationInfo))
        # test with a more deeply nested model instance
        self.assertSetEqual(set((self.test_res_1,)),
            get_root_resources(*self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all()))
        # test with twice the same more deeply nested model instance
        self.assertSetEqual(set((self.test_res_1,)),
            get_root_resources(*(list(self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all())
                + list(self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all()))))
        # test with two different nested model instances of the same resource
        self.assertSetEqual(set((self.test_res_1,)),
            get_root_resources(*(list(self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all())
                + list(self.test_res_1.metadataInfo.metadataCreator.all()))))
        # test with two nested model instances of different resources
        self.assertSetEqual(set((self.test_res_1, self.test_res_2)),
            get_root_resources(*(list(self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all())
                + list(self.test_res_2.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all()))))
        # test with multiple nested model instances of different resources
        self.assertSetEqual(set((self.test_res_1, self.test_res_2)),
            get_root_resources(*(list(self.test_res_1.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all())
                + list(self.test_res_2.resourceComponentType \
                    .as_subclass().corpusMediaType \
                    .corpustextinfotype_model_set.all())
                + list(self.test_res_1.metadataInfo.metadataCreator.all())
                + list(self.test_res_2.contactPerson.all())
                + [self.test_res_1.identificationInfo,
                   self.test_res_2.identificationInfo])))
