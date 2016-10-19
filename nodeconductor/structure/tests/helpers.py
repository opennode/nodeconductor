from ddt import data
from django.core.exceptions import ObjectDoesNotExist

from . import factories
from .. import models


class _cached_class_property(object):
    """ Allows to reach classmethod as property and cache returned value in class """

    def __init__(self, method):
        self.method = method
        self.cache_name = self.method.__name__ + '_cached'

    def __get__(self, owner_self, owner_cls):
        try:
            value = getattr(owner_cls, self.cache_name)
            value.refresh_from_db()
        except (AttributeError, ObjectDoesNotExist):
            value = self.method(owner_cls)
            setattr(owner_cls, self.cache_name, value)
        return value


class test_data(object):
    """ Container with standard structure objects that can be used for testing.

        Use test_data as enum:

            def test_admin_can_reach_project(self):
                self.client.force_authenticate(user=test_data.admin)
                url = factories.ProjectFactory.get_url(test_data.project)
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        Use test_data with ddt as decorator:

            @ddt
            class MyTest(TransactionTestCase):

                @test_data('staff', 'admin', 'owner', 'manager')
                def test_user_can_reach_project(self, user):
                    self.client.force_authenticate(user=user)
                    url = factories.ProjectFactory.get_url(test_data.project)
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
    """

    def __init__(self, *args):
        self.args = args

    def __call__(self, method):
        @data(*self.args)
        def wrapped(self, *method_args):
            method_args = [getattr(test_data, arg) for arg in method_args]
            return method(self, *method_args)
        return wrapped

    @_cached_class_property
    def customer(cls):
        return factories.CustomerFactory()

    @_cached_class_property
    def service_settings(cls):
        return factories.ServiceSettingsFactory(customer=cls.customer)

    @_cached_class_property
    def project(cls):
        return factories.ProjectFactory(customer=cls.customer)

    @_cached_class_property
    def service(cls):
        return factories.TestServiceFactory(service_settings=cls.service_settings, customer=cls.customer)

    @_cached_class_property
    def service_project_link(cls):
        return factories.TestServiceProjectLinkFactory(service=cls.service, project=cls.project)

    @_cached_class_property
    def instance(cls):
        return factories.TestInstanceFactory(service_project_link=cls.service_project_link)

    @_cached_class_property
    def staff(cls):
        return factories.UserFactory(is_staff=True)

    @_cached_class_property
    def user(cls):
        return factories.UserFactory()

    @_cached_class_property
    def owner(cls):
        owner = factories.UserFactory()
        cls.customer.add_user(owner, models.CustomerRole.OWNER)
        return owner

    @_cached_class_property
    def admin(cls):
        admin = factories.UserFactory()
        cls.project.add_user(admin, models.ProjectRole.ADMINISTRATOR)
        return admin

    @_cached_class_property
    def manager(cls):
        manager = factories.UserFactory()
        cls.project.add_user(manager, models.ProjectRole.MANAGER)
        return manager
