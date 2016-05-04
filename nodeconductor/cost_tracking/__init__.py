"""
Cost tracking - add-on for NC plugins.


Add-on adds next functional to plugin:

 - calculate and store price estimate for each resource, service, project, customer.
 - register resource used items (ex: CPU, storage for VMs) prices and show their prices for resource cost calculation.
 - get resource used items for current moment.


Add-on connection:

    1. Implement CostTrackingBackend interface.

        class IaaSCostTrackingBackend(CostTrackingBackend):
            ...

    2. Add application to add-on register.

        CostTrackingRegister.register(self.label, cost_tracking.IaaSCostTrackingBackend)

"""
import logging
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch

from nodeconductor.structure import ServiceBackendNotImplemented


default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'
logger = logging.getLogger(__name__)


class CostTrackingRegister(object):
    """ Register of all connected NC plugins """

    _register = {}

    @classmethod
    def register(cls, app_label, backend):
        cls._register[app_label] = backend

    @classmethod
    def get_registered_backends(cls):
        return cls._register.values()

    @classmethod
    def get_resource_backend(cls, resource):
        try:
            return cls._register[resource._meta.app_label]
        except KeyError:
            raise ServiceBackendNotImplemented


class CostTrackingBackend(object):
    """ Cost tracking interface for NC plugin """

    # A list of numerical <item type>'s like storage or users count
    NUMERICAL = []

    # Should be used as consistent name for different VM types
    VM_SIZE_ITEM_TYPE = 'flavor'

    @classmethod
    def get_used_items(cls, resource):
        """ Return list of items that are currently used by resource

        Return format: [(<item type>, <item name>, <item usage>), ...]
        <item usage> should be 1 for all uncountable items (flavors, installed OS ...)
        """
        raise NotImplementedError()

    @classmethod
    def get_service_price_list_items(cls, service):
        """ Return list of price items for concrete service """
        raise NotImplementedError()

    @classmethod
    def get_default_price_list_items(cls):
        """ Return list of default price items for application """
        raise NotImplementedError()

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        """ Get resource monthly cost estimate.

        By default monthly cost estimate is calculated as multiplication
        of default price list items prices on used items time.
        Cost estimate is calculated using price list of resource's service if possible.

        Method should return decimal as result.
        """
        price_map = cls._get_price_map(resource)

        monthly_cost = 0
        for item_type, item_key, item_count in cls.get_used_items(resource):
            key = (item_type, item_key)
            value = price_map.get(key)
            if value is None:
                logger.error('Can not find price item with key "%s" and type "%s" for resource "%s"',
                             item_key, item_type, resource)
            else:
                monthly_cost += value * Decimal(format(item_count, ".15g"))
        return monthly_cost

    @classmethod
    def _get_price_map(cls, resource):
        from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceListItem
        resource_content_type = ContentType.objects.get_for_model(resource)

        price_list_items = models.PriceListItem.objects.filter(service=resource.service_project_link.service)
        prefetch = Prefetch('pricelistitem_set', queryset=price_list_items, to_attr='service_item')

        price_items = DefaultPriceListItem.objects\
            .filter(resource_content_type=resource_content_type)\
            .prefetch_related(prefetch)

        price_map = {}
        for item in price_items:
            key = (item.item_type, item.key)
            val = item.monthly_rate
            if item.service_item:
                val = item.service_item[0].monthly_rate
            price_map[key] = Decimal(val)
        return price_map
