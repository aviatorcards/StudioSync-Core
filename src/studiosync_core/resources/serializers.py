from rest_framework import serializers

from .models import Resource, ResourceCheckout, ResourceFolder, Setlist, SetlistResource


class ResourceFolderSerializer(serializers.ModelSerializer):
    """Serializer for virtual resource folders."""

    children_count = serializers.SerializerMethodField()
    resources_count = serializers.SerializerMethodField()

    class Meta:
        model = ResourceFolder
        fields = [
            "id",
            "name",
            "parent",
            "children_count",
            "resources_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by"]

    def get_children_count(self, obj):
        return obj.children.count()

    def get_resources_count(self, obj):
        return obj.resources.count()


class ResourceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.FileField(source="file", read_only=True)
    folder_name = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "description",
            "resource_type",
            "file",
            "file_url",
            "external_url",
            "tags",
            "category",
            "folder",
            "folder_name",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
            "is_public",
            "is_lendable",
            "quantity_available",
            "band",
            "instrument",
            "composer",
            "key_signature",
            "tempo",
        ]
        read_only_fields = ["uploaded_by", "file_size"]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return "Unknown"

    def get_folder_name(self, obj):
        return obj.folder.name if obj.folder else None

    def create(self, validated_data):
        # Handle tags from FormData (may come as JSON string)
        if "tags" in validated_data and isinstance(validated_data["tags"], str):
            import json

            try:
                validated_data["tags"] = json.loads(validated_data["tags"])
            except (json.JSONDecodeError, TypeError):
                validated_data["tags"] = []

        # Set file size if file is present
        if "file" in validated_data and validated_data["file"]:
            validated_data["file_size"] = validated_data["file"].size

        return super().create(validated_data)

    def validate(self, data):
        """Validate that music resources have required fields"""
        resource_type = data.get("resource_type")
        music_types = ["sheet_music", "chord_chart", "tablature", "lyrics"]

        if resource_type in music_types:
            if not data.get("instrument"):
                raise serializers.ValidationError(
                    {"instrument": "Instrument is required for music resources"}
                )

        return data


class ResourceCheckoutSerializer(serializers.ModelSerializer):
    """Serializer for resource checkouts"""

    resource_title = serializers.ReadOnlyField(source="resource.title")
    student_name = serializers.ReadOnlyField(source="student.user.get_full_name")
    is_overdue = serializers.ReadOnlyField()

    class Meta:
        model = ResourceCheckout
        fields = [
            "id",
            "resource",
            "resource_title",
            "student",
            "student_name",
            "status",
            "checked_out_at",
            "due_date",
            "returned_at",
            "checkout_notes",
            "return_notes",
            "is_overdue",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["checked_out_at", "created_at", "updated_at"]


class SetlistResourceSerializer(serializers.ModelSerializer):
    """Serializer for items within a setlist"""

    resource = ResourceSerializer(read_only=True)

    class Meta:
        model = SetlistResource
        fields = ["id", "order", "resource"]


class SetlistSerializer(serializers.ModelSerializer):
    """Serializer for a setlist of resources"""

    resources = SetlistResourceSerializer(source="setlistresource_set", many=True, read_only=True)
    created_by_name = serializers.ReadOnlyField(source="created_by.get_full_name")

    class Meta:
        model = Setlist
        fields = [
            "id",
            "name",
            "description",
            "studio",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
            "resources",
        ]
        read_only_fields = ["studio", "created_by"]
