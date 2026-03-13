from rest_framework import serializers

from studiosync_core.core.models import Family, Student, User


class ParentSerializer(serializers.ModelSerializer):
    """Simple serializer for parent user info"""

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "phone"]
        read_only_fields = [
            "email"
        ]  # Email usually unchangeable here for security, or managed via main User serializer


class FamilyMemberSerializer(serializers.ModelSerializer):
    """Simple student info for family view"""

    name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Student
        fields = ["id", "name", "instrument"]


class FamilySerializer(serializers.ModelSerializer):
    """Serializer for Family model with nested parents and children"""

    primary_parent_details = ParentSerializer(source="primary_parent", read_only=True)
    secondary_parent_details = ParentSerializer(source="secondary_parent", read_only=True)
    students = FamilyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Family
        fields = [
            "id",
            "studio",
            "primary_parent",
            "primary_parent_details",
            "secondary_parent",
            "secondary_parent_details",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "billing_email",
            "students",
            "created_at",
        ]
        read_only_fields = ["studio", "created_at"]
