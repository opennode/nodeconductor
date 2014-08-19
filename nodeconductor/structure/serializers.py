from __future__ import unicode_literals

from django.contrib.auth import models as auth_models

from rest_framework import serializers

from nodeconductor.structure import models


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Customer
        fields = ('url', 'name', 'abbreviation', 'contact_details')
        lookup_field = 'uuid'


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Project
        fields = ('url', 'name')
        lookup_field = 'uuid'


class ProjectGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name')
        lookup_field = 'uuid'


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = auth_models.User
        fields = ('username', 'first_name', 'last_name')
        lookup_field = 'username'
