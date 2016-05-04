from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch

from rest_framework import viewsets, permissions, exceptions, decorators, response, status

from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.cost_tracking import models, serializers, filters
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import ScopeTypeFilterBackend


class PriceEditPermissionMixin(object):

    def can_user_modify_price_object(self, scope):
        if self.request.user.is_staff:
            return True
        customer = reduce(getattr, scope.Permissions.customer_path.split('__'), scope)
        if customer.has_user(self.request.user, structure_models.CustomerRole.OWNER):
            return True
        return False


class PriceEstimateViewSet(PriceEditPermissionMixin, viewsets.ModelViewSet):
    queryset = models.PriceEstimate.objects.all()
    serializer_class = serializers.PriceEstimateSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.AdditionalPriceEstimateFilterBackend,
        filters.PriceEstimateScopeFilterBackend,
        ScopeTypeFilterBackend,
        DjangoMappingFilterBackend,
    )
    filter_class = filters.PriceEstimateFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == 'threshold':
            return serializers.PriceEstimateThresholdSerializer
        elif self.action == 'limit':
            return serializers.PriceEstimateLimitSerializer
        return self.serializer_class

    def get_queryset(self):
        return models.PriceEstimate.objects.filtered_for_user(self.request.user).filter(is_visible=True).order_by(
            '-year', '-month')

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['scope']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceEstimateViewSet, self).perform_create(serializer)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'destroy', 'update'):
            price_estimate = self.get_object()
            if not price_estimate.is_manually_input:
                raise exceptions.MethodNotAllowed('Auto calculated price estimate can not be edited or deleted')
            if not self.can_user_modify_price_object(price_estimate.scope):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceEstimateViewSet, self).initial(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """
        To get a list of price estimates, run **GET** against */api/price-estimates/* as authenticated user.

        `scope_type` is generic type of object for which price estimate is calculated.
        Currently there are following types: customer, project, serviceprojectlink, service, resource.

        Run **POST** against */api/price-estimates/* to create price estimate. Manually created price estimate
        will replace auto calculated estimate. Manual creation is available only for estimates for resources and
        service-project-links. Only customer owner and staff can edit price estimates.

        Request example:

        .. code-block:: http

            POST /api/price-estimates/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/instances/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "total": 1000,
                "consumed": 800,
                "month": 8,
                "year": 2015
            }
        """

        return super(PriceEstimateViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Run **PATCH** request against */api/price-estimates/<uuid>/* to update manually created price estimate.
        Only fields "total" and "consumed" could be updated. Only customer owner
        and staff can update price estimates.

        Run **DELETE** request against */api/price-estimates/<uuid>/* to delete price estimate. Estimate will be
        replaced with auto calculated (if it exists). Only customer owner and staff can delete price estimates.
        """
        return super(PriceEstimateViewSet, self).retrieve(request, *args, **kwargs)

    @decorators.list_route(methods=['post'])
    def threshold(self, request, **kwargs):
        """
        Run **POST** request against */api/price-estimates/threshold/*
        to set alert threshold for price estimate.
        Example request:

        .. code-block:: http

            POST /api/price-estimates/threshold/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/projects/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "threshold": 100.0
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        threshold = serializer.validated_data['threshold']
        scope = serializer.validated_data['scope']

        if not self.can_user_modify_price_object(scope):
            raise exceptions.PermissionDenied()

        models.PriceEstimate.objects.create_or_update(scope, threshold=threshold)
        return response.Response({'detail': 'Threshold for price estimate is updated'},
                                 status=status.HTTP_200_OK)

    @decorators.list_route(methods=['post'])
    def limit(self, request, **kwargs):
        """
        Run **POST** request against */api/price-estimates/limit/*
        to set price estimate limit. When limit is set, provisioning is disabled
        if total estimated monthly cost of project and resource exceeds project cost limit.
        If limit is -1, project cost limit do not apply. Example request:

        .. code-block:: http

            POST /api/price-estimates/limit/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/projects/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "limit": 100.0
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        limit = serializer.validated_data['limit']
        scope = serializer.validated_data['scope']

        if not self.can_user_modify_price_object(scope):
            raise exceptions.PermissionDenied()

        models.PriceEstimate.objects.create_or_update(scope, limit=limit)
        return response.Response({'detail': 'Limit for price estimate is updated'},
                                 status=status.HTTP_200_OK)


class PriceListItemViewSet(PriceEditPermissionMixin, viewsets.ModelViewSet):
    queryset = models.PriceListItem.objects.all()
    serializer_class = serializers.PriceListItemSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.PriceListItemServiceFilterBackend,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceListItem.objects.filtered_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        """
        To get a list of price list items, run **GET** against */api/price-list-items/* as an authenticated user.
        """
        return super(PriceListItemViewSet, self).list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Run **POST** request against */api/price-list-items/* to create new price list item.
        Customer owner and staff can create price items.

        Example of request:

        .. code-block:: http

            POST /api/price-list-items/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "units": "per month",
                "value": 100,
                "service": "http://example.com/api/oracle/d4060812ca5d4de390e0d7a5062d99f6/",
                "default_price_list_item": "http://example.com/api/default-price-list-items/349d11e28f634f48866089e41c6f71f1/"
            }
        """
        return super(PriceListItemViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Run **PATCH** request against */api/price-list-items/<uuid>/* to update price list item.
        Only item_type, key value and units can be updated.
        Only customer owner and staff can update price items.
        """
        return super(PriceListItemViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Run **DELETE** request against */api/price-list-items/<uuid>/* to delete price list item.
        Only customer owner and staff can delete price items.
        """
        return super(PriceListItemViewSet, self).destroy(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'update', 'destroy'):
            price_list_item = self.get_object()
            if not self.can_user_modify_price_object(price_list_item.service):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceListItemViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['service']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceListItemViewSet, self).perform_create(serializer)


class DefaultPriceListItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.DefaultPriceListItem.objects.all()
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = filters.DefaultPriceListItemFilter
    filter_backends = (DjangoMappingFilterBackend,)
    serializer_class = serializers.DefaultPriceListItemSerializer

    def list(self, request, *args, **kwargs):
        """
        To get a list of default price list items, run **GET** against */api/default-price-list-items/*
        as authenticated user.

        Price lists can be filtered by:
         - ?key=<string>
         - ?item_type=<string> has to be from list of available item_types
           (available options: 'flavor', 'storage', 'license-os', 'license-application', 'network', 'support')
         - ?resource_type=<string> resource type, for example: 'OpenStack.Instance, 'Oracle.Database')
        """
        return super(DefaultPriceListItemViewSet, self).list(request, *args, **kwargs)


class MergedPriceListItemViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = filters.DefaultPriceListItemFilter
    filter_backends = (DjangoMappingFilterBackend,)
    serializer_class = serializers.MergedPriceListItemSerializer

    def list(self, request, *args, **kwargs):
        """
        To get a list of price list items, run **GET** against */api/merged-price-list-items/*
        as authenticated user.

        If service is not specified default price list items are displayed.
        Otherwise service specific price list items are displayed.
        In this case rendered object contains {"is_manually_input": true}

        In order to specify service pass query parameters:
        - service_type (Azure, OpenStack etc.)
        - service_uuid

        Example URL: http://example.com/api/merged-price-list-items/?service_type=Azure&service_uuid=cb658b491f3644a092dd223e894319be

        """
        return super(MergedPriceListItemViewSet, self).list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = models.DefaultPriceListItem.objects.all()
        service = self._find_service()
        if service:
            price_list_items = models.PriceListItem.objects.filter(service=service)
            prefetch = Prefetch('pricelistitem_set', queryset=price_list_items, to_attr='service_item')
            queryset = queryset.prefetch_related(prefetch)
        return queryset

    def _find_service(self):
        from nodeconductor.structure import SupportedServices

        service_type = self.request.query_params.get('service_type')
        service_uuid = self.request.query_params.get('service_uuid')
        if not service_type or not service_uuid:
            return
        rows = SupportedServices.get_service_models()
        if service_type not in rows:
            return
        service_class = rows.get(service_type)['service']
        try:
            return service_class.objects.get(uuid=service_uuid)
        except ObjectDoesNotExist:
            return None

    def list(self, request, *args, **kwargs):
        return super(MergedPriceListItemViewSet, self).list(request, *args, **kwargs)
