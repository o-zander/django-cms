# -*- coding: utf-8 -*-

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.forms.models import ModelForm
from django.utils.encoding import smart_text
from django.utils.translation import ugettext as _

from cms.api import create_page
from cms.constants import TEMPLATE_INHERITANCE_MAGIC
from cms.models import Page, UserSettings
from cms.test_utils.testcases import CMSTestCase, TransactionCMSTestCase
from cms.wizards.wizard_base import Wizard
from cms.wizards.wizard_pool import wizard_pool, AlreadyRegisteredException


class WizardForm(forms.Form):
    pass


class ModelWizardForm(ModelForm):
    class Meta:
        model = UserSettings


class BadModelForm(ModelForm):
    class Meta:
        pass


class WizardTestMixin(object):
    page_wizard = None
    title_wizard = None

    @classmethod
    def setUpClass(cls):
        super(WizardTestMixin, cls).setUpClass()
        # This prevents auto-discovery, which would otherwise occur as soon as
        # tests start, creating unexpected starting conditions.
        wizard_pool._discovered = True

        # This is a basic Wizard
        cls.page_wizard = Wizard(
            title=_(u"Page"),
            weight=100,
            form=WizardForm,
            model=Page,
            template_name='my_template.html',  # This doesn't exist anywhere
        )

        # This is a Wizard that uses a ModelForm to define the model
        cls.user_settings_wizard = Wizard(
            title=_(u"UserSettings"),
            weight=200,
            form=ModelWizardForm,
        )

        # This is a bad wizard definition as it neither defines a model, nor
        # uses a ModelForm that has model defined in Meta
        cls.title_wizard = Wizard(
            title=_(u"Page"),
            weight=100,
            form=BadModelForm,
            template_name='my_template.html',  # This doesn't exist anywhere
        )


class TestWizardBase(WizardTestMixin, TransactionCMSTestCase):

    def test_str(self):
        self.assertEqual(str(self.page_wizard), self.page_wizard.title)

    def test_repr(self):
        self.assertEqual(self.page_wizard.__repr__(), 'Wizard: "Page"')

    def test_user_has_add_permission(self):
        # Test does not have permission
        user = self.get_staff_user_with_no_permissions()
        self.assertFalse(self.page_wizard.user_has_add_permission(user))

        # Test has permission
        user = self.get_superuser()
        self.assertTrue(self.page_wizard.user_has_add_permission(user))

    def test_get_success_url(self):
        user = self.get_superuser()
        page = create_page(
            title="Sample Page",
            template=TEMPLATE_INHERITANCE_MAGIC,
            language="en",
            created_by=smart_text(user),
            parent=None,
            in_navigation=True,
            published=False
        )
        url = page.get_absolute_url(language="en")
        self.assertEqual(
            self.page_wizard.get_success_url(page, language="en"), url)

        # Now again without a language code
        url = page.get_absolute_url()
        self.assertEqual(self.page_wizard.get_success_url(page), url)

    def test_get_model(self):
        self.assertEqual(self.page_wizard.get_model(), Page)
        self.assertEqual(self.user_settings_wizard.get_model(), UserSettings)
        with self.assertRaises(ImproperlyConfigured):
            self.title_wizard.get_model()


class TestWizardPool(WizardTestMixin, CMSTestCase):

    def test_discover(self):
        """
        Tests that _discover() will register the page wizard.
        """
        wizard_pool._reset()
        self.assertFalse(wizard_pool._discovered)
        self.assertEqual(len(wizard_pool._entries), 0)
        wizard_pool._discover()
        self.assertTrue(len(wizard_pool._entries) > 0)
        self.assertTrue(wizard_pool._discovered)

    def test_register_unregister_isregistered(self):
        wizard_pool._clear()
        self.assertEqual(len(wizard_pool._entries), 0)
        wizard_pool.register(self.page_wizard)
        # Now, try to register the same thing
        with self.assertRaises(AlreadyRegisteredException):
            wizard_pool.register(self.page_wizard)

        self.assertEqual(len(wizard_pool._entries), 1)
        self.assertTrue(wizard_pool.is_registered(self.page_wizard))
        self.assertTrue(wizard_pool.unregister(self.page_wizard))
        self.assertEqual(len(wizard_pool._entries), 0)

        # Now, try to unregister something that is not registered
        self.assertFalse(wizard_pool.unregister(self.user_settings_wizard))

    def test_get_entry(self):
        wizard_pool._clear()
        wizard_pool.register(self.page_wizard)
        entry = wizard_pool.get_entry(self.page_wizard)
        self.assertEqual(entry, self.page_wizard)

    def test_get_entries(self):
        """
        Test that the registered entries are returned in weight-order, no matter
        which order they were added.
        """
        wizard_pool._clear()
        wizard_pool.register(self.page_wizard)
        wizard_pool.register(self.user_settings_wizard)
        wizards = [self.page_wizard, self.user_settings_wizard]
        wizards.sort(key=lambda e: getattr(e, 'weight'))
        entries = wizard_pool.get_entries()
        self.assertItemsEqual(entries, wizards)

        wizard_pool._clear()
        wizard_pool.register(self.user_settings_wizard)
        wizard_pool.register(self.page_wizard)
        wizards = [self.page_wizard, self.user_settings_wizard]
        wizards.sort(key=lambda e: getattr(e, 'weight'))
        entries = wizard_pool.get_entries()
        self.assertItemsEqual(entries, wizards)
