from rest_framework import serializers

from nodeconductor.cloud import models


class CloudSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name')
        lookup_field = 'uuid'


class FlavorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Flavor
        fields = ('url', 'name', 'ram', 'disk', 'cores')
        lookup_field = 'uuid'
