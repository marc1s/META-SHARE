from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User, Permission
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from metashare import test_utils
from metashare.accounts.models import UserProfile
from metashare.repository.models import resourceInfoType_model
from metashare.repository import views
from metashare.settings import DJANGO_BASE, ROOT_PATH
from metashare.test_utils import create_user


def _import_resource(fixture_name):
    """
    Imports the XML resource description with the given file name.
    
    The new resource is published and returned.
    """
    result = test_utils.import_xml('{0}/repository/fixtures/{1}'
                                    .format(ROOT_PATH, fixture_name))[0]
    result.storage_object.published = True
    result.storage_object.save()
    return result


class ViewTest(TestCase):
    """
    Test the detail view
    """
    def setUp(self):
        """
        Set up the detail view
        """
        test_utils.setup_test_storage()
        self.resource = _import_resource('testfixture.xml')
        # set up test users with and without staff permissions.
        # These will live in the test database only, so will not
        # pollute the "normal" development db or the production db.
        # As a consequence, they need no valuable password.
        staffuser = create_user('staffuser', 'staff@example.com', 'secret')
        staffuser.is_staff = True
        staffuser.save()
        create_user('normaluser', 'normal@example.com', 'secret')

    def tearDown(self):
        """
        Clean up the test
        """
        resourceInfoType_model.objects.all().delete()
        User.objects.all().delete()

    def testView(self):
        """
        Tries to view a resource
        """
        client = Client()
        url = self.resource.get_absolute_url()
        response = client.get(url, follow = True)
        self.assertTemplateUsed(response, 'repository/lr_view.html')
        self.assertNotContains(response, "Edit")

    def test_staff_user_sees_editor(self):
        """
        Tests whether a staff user can edit a resource (in seeing the edit button)
        """
        client = Client()
        client.login(username='staffuser', password='secret')
        url = self.resource.get_absolute_url()
        response = client.get(url, follow = True)
        self.assertTemplateUsed(response, 'repository/lr_view.html')
        self.assertContains(response, "Editor")

    def test_normal_user_doesnt_see_editor(self):
        """
        Tests whether a normal user cannot edit a resource
        """
        client = Client()
        client.login(username='normaluser', password='secret')
        url = self.resource.get_absolute_url()
        response = client.get(url, follow = True)
        self.assertTemplateUsed(response, 'repository/lr_view.html')
        self.assertNotContains(response, "Editor")

    def test_anonymous_doesnt_see_editor(self):
        """
        Tests whether an anonymous user cannot edit a resource
        """
        client = Client()
        url = self.resource.get_absolute_url()
        response = client.get(url, follow = True)
        self.assertTemplateUsed(response, 'repository/lr_view.html')
        self.assertNotContains(response, "Editor")


class DownloadViewTest(TestCase):
    """
    Tests for the license selection, license agreement and download views.
    """
    def setUp(self):
        """
        Sets up some resources with which to test.
        """
        test_utils.setup_test_storage()
        # set up different test resources
        self.non_downloadable_resource = _import_resource('testfixture.xml')
        self.downloadable_resource_1 = \
            _import_resource('downloadable_1_license.xml')
        self.ms_commons_resource = \
            _import_resource('downloadable_ms_commons_license.xml')
        # set up test users with/without staff permissions and with/without
        # META-SHARE full membership
        staffuser = create_user('staffuser', 'staff@example.com', 'secret')
        staffuser.is_staff = True
        staffuser.save()
        create_user('normaluser', 'normal@example.com', 'secret')
        profile_ct = ContentType.objects.get_for_model(UserProfile)
        ms_member = create_user('fullmember', 'fm@example.com', 'secret')
        ms_member.user_permissions.add(Permission.objects.get(
                    content_type=profile_ct, codename='ms_full_member'))
        ms_member.save()
        ms_member = create_user('associatemember', 'am@example.com', 'secret')
        ms_member.user_permissions.add(Permission.objects.get(
                    content_type=profile_ct, codename='ms_associate_member'))
        ms_member.save()

    def tearDown(self):
        """
        Cleans up the test environment.
        """
        resourceInfoType_model.objects.all().delete()
        User.objects.all().delete()

    def test_non_downloadable_resource(self):
        """
        Verifies that an information page is provided for resources which are
        not marked as downloadable.
        """
        # make sure a staff user gets the information page:
        client = Client()
        client.login(username='staffuser', password='secret')
        response = client.get(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/lr_not_downloadable.html')
        # make sure a normal user gets the information page, too:
        client = Client()
        client.login(username='normaluser', password='secret')
        response = client.get(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/lr_not_downloadable.html')

    def test_downloadable_resource_with_one_license(self):
        """
        Verifies that a resource with only one download license (possibly
        amongst various other distribution licenses) can be downloaded
        appropriately.
        """
        # test as staff user:
        client = Client()
        client.login(username='staffuser', password='secret')
        self._test_downloadable_resource_with_one_license(client)
        # test as normal user:
        client = Client()
        client.login(username='normaluser', password='secret')
        self._test_downloadable_resource_with_one_license(client)

    def _test_downloadable_resource_with_one_license(self, client):
        """
        Verifies that a resource with only one download license (possibly
        amongst various other distribution licenses) can be downloaded
        appropriately using the given client.
        """
        # make sure the license page is shown:
        response = client.get(reverse(views.download,
                args=(self.downloadable_resource_1.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response, 'licences/CC-BYNCSAv2.5.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # make sure the license agreement page is shown again if the license was
        # not accepted:
        response = client.post(reverse(views.download,
                args=(self.downloadable_resource_1.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'False',
              'licence': 'CC_BY-NC-SA' },
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response, 'licences/CC-BYNCSAv2.5.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # make sure the download was started after accepting the license:
        response = client.post(reverse(views.download,
                args=(self.downloadable_resource_1.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'True',
              'licence': 'CC_BY-NC-SA' },
            follow = True)
        self.assertTemplateNotUsed(response, 'repository/licence_agreement.html',
                            msg_prefix="a download should have been started")
        self.assertTemplateNotUsed(response, 'repository/licence_selection.html',
                            msg_prefix="a download should have been started")
        self.assertTemplateNotUsed(response, 'repository/lr_not_downloadable.html',
                            msg_prefix="a download should have been started")

    def test_downloadable_resource_with_multiple_licenses(self):
        """
        Verifies that a resource with multiple download licenses (possibly
        amongst various other distribution licenses) can be downloaded
        appropriately.
        """
        # TODO add assertions
        pass

    def test_locally_downloadable_resource(self):
        """
        Verifies that a resource which is locally downloadable can actually be
        downloaded appropriately.
        """
        # TODO add assertions
        pass

    def test_externally_downloadable_resource(self):
        """
        Verifies that a resource which is externally downloadable can actually
        be downloaded appropriately.
        """
        client = Client()
        client.login(username='normaluser', password='secret')
        response = client.post(reverse(views.download, args=
                (self.downloadable_resource_1.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'True',
              'licence': 'CC_BY-NC-SA' },
            follow = True)
        self.assertIn(("http://www.example.org/dl1", 302),
                      response.redirect_chain,
                      msg="There should be a redirect to example.org.")

    def test_resource_download_as_anonymous_user(self):
        """
        Verifies that the anonymous user cannot download any resources.
        """
        # neither via GET ...
        response = Client().get(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'login.html')
        # ... nor via POST with no data ...
        response = Client().post(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'login.html')
        # ... nor via POST with a selected license ...
        response = Client().post(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            { 'licence': 'GPL' },
            follow = True)
        # ... nor via POST with an agreement to some license:
        response = Client().post(reverse(views.download, args=
                (self.non_downloadable_resource.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'True',
              'licence': 'GPL' },
            follow = True)
        self.assertTemplateUsed(response, 'login.html')

    def test_download_button_is_correct_with_staff_user(self):
        """
        Tests whether the link of the download button is the good one
        """
        client = Client()
        client.login(username='staffuser', password='secret')
        url = self.downloadable_resource_1.get_absolute_url()
        response = client.get(url, follow = True)
        self.assertTemplateUsed(response, 'repository/lr_view.html')
        self.assertContains(response, "repository/download/{0}".format(
                        self.downloadable_resource_1.storage_object.identifier))

    def test_resource_download_as_unauthorized_user(self):
        """
        Verifies that a non-authorized user cannot download certain resources.
        """
        client = Client()
        client.login(username='associatemember', password='secret')
        # make sure the license page is shown on both a GET and a POST request
        # with no data:
        response = client.get(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        response = client.post(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # LR must not be downloadable via POST with just a selected license ...
        response = client.post(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            { 'licence': 'MSCommons_BY-NC-SA' },
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # ... nor via POST with an agreement to the license:
        response = client.post(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'True',
              'licence': 'MSCommons_BY-NC-SA' },
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")

    def test_downloadable_resource_for_ms_full_members(self):
        """
        Verifies that a resource with an MS Commons license can be downloaded by
        a META-SHARE full member.
        """
        client = Client()
        client.login(username='fullmember', password='secret')
        # make sure the license page is shown:
        response = client.get(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # make sure the license agreement page is shown again if the license was
        # not accepted:
        response = client.post(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'False',
              'licence': 'MSCommons_BY-NC-SA' },
            follow = True)
        self.assertTemplateUsed(response, 'repository/licence_agreement.html',
                                "license agreement page expected")
        self.assertContains(response,
                            'licences/META-SHARE_COMMONS_BYNCSA_v1.0.htm',
                            msg_prefix="the correct license appears to not " \
                                "be shown in an iframe")
        # make sure the download was started after accepting the license:
        response = client.post(reverse(views.download,
                    args=(self.ms_commons_resource.storage_object.identifier,)),
            { 'in_licence_agree_form': 'True', 'licence_agree': 'True',
              'licence': 'MSCommons_BY-NC-SA' },
            follow = True)
        self.assertTemplateNotUsed(response, 'repository/licence_agreement.html',
                            msg_prefix="a download should have been started")
        self.assertTemplateNotUsed(response, 'repository/licence_selection.html',
                            msg_prefix="a download should have been started")
        self.assertTemplateNotUsed(response, 'repository/lr_not_downloadable.html',
                            msg_prefix="a download should have been started")

    def test_can_download_master_copy(self):        
        client = Client()
        client.login(username='staffuser', password='secret')
        self.downloadable_resource_1.storage_object.master_copy = True
        self.downloadable_resource_1.storage_object.save()
        response = client.get('/{0}repository/download/{1}/'
                              .format(DJANGO_BASE, self.downloadable_resource_1.storage_object.identifier))
        self.assertContains(response, "I agree to these licence terms")        
        
    def test_cannot_download_not_master_copy(self):
        client = Client()
        client.login(username='staffuser', password='secret')
        self.downloadable_resource_1.storage_object.master_copy = False
        self.downloadable_resource_1.storage_object.save()
        response = client.get('/{0}repository/download/{1}/'
                              .format(DJANGO_BASE, self.downloadable_resource_1.storage_object.identifier))
        self.assertContains(response, "You will now be redirected")
