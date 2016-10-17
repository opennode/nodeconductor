from django.contrib.auth import get_user_model
from rest_framework import serializers

from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.structure import models as structure_models
from nodeconductor.users import models

User = get_user_model()


class InvitationSerializer(serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='project_role.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=structure_models.Project.objects.all(),
        required=False,
        allow_null=True
    )
    project_role = MappedChoiceField(
        source='project_role.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': structure_models.ProjectRole.ADMINISTRATOR,
            'manager': structure_models.ProjectRole.MANAGER,
        },
        required=False,
        allow_null=True
    )
    customer = serializers.HyperlinkedRelatedField(
        source='customer_role.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=structure_models.Customer.objects.all(),
        required=False,
        allow_null=True
    )
    customer_role = MappedChoiceField(
        source='customer_role.role_type',
        choices=(
            ('owner', 'Owner'),
        ),
        choice_mappings={
            'owner': structure_models.CustomerRole.OWNER,
        },
        required=False,
        allow_null=True
    )

    expires = serializers.DateTimeField(source='get_expiration_time', read_only=True)

    class Meta(object):
        model = models.Invitation
        fields = ('url', 'uuid', 'state', 'link_template', 'email',
                  'project', 'project_role', 'customer', 'customer_role', 'created', 'expires')
        read_only_fields = ('url', 'uuid', 'state', 'created', 'expires')
        view_name = 'user-invitation-detail'
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('User with provided email already exists.')

        return email

    def validate(self, attrs):
        link_template = attrs['link_template']
        if '{uuid}' not in link_template:
            raise serializers.ValidationError({'link_template': "Link template must include '{uuid}' parameter."})

        customer_role = attrs.get('customer_role', {})
        project_role = attrs.get('project_role', {})
        project = project_role.get('project')
        customer = customer_role.get('customer')
        if customer and project:
            raise serializers.ValidationError('Cannot create invitation to project and customer simultaneously.')
        elif not (customer or project):
            raise serializers.ValidationError('Customer or project must be provided.')
        elif customer and customer_role.get('role_type') is None:
            raise serializers.ValidationError({'customer_role': 'Customer role must be provided.'})
        elif project and project_role.get('role_type') is None:
            raise serializers.ValidationError({'project_role': 'Project role must be provided.'})

        return attrs

    def create(self, validated_data):
        project_role_data = validated_data.pop('project_role', {})
        customer_role_data = validated_data.pop('customer_role', {})

        if project_role_data:
            project = project_role_data['project']
            project_role = project.roles.get(role_type=project_role_data['role_type'])
            validated_data['project_role'] = project_role
            validated_data['customer'] = project.customer
        elif customer_role_data:
            customer = customer_role_data['customer']
            customer_role = customer.roles.get(role_type=customer_role_data['role_type'])
            validated_data['customer_role'] = customer_role
            validated_data['customer'] = customer

        return super(InvitationSerializer, self).create(validated_data)


class AcceptInvitationSerializer(serializers.Serializer):
        user = serializers.HyperlinkedRelatedField(
            view_name='user-detail',
            lookup_field='uuid',
            queryset=User.objects.all()
        )
