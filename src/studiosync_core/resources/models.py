"""
Resource models - Resource for file/media management
"""

import uuid

from django.db import models
from django.utils import timezone

from studiosync_core.core.models import Student, Studio, User


class ResourceFolder(models.Model):
    """
    A virtual folder for organising digital resources, like a Google Drive folder.
    Folders are scoped to a studio and support unlimited nesting via a self-referencing FK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="resource_folders")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent folder. Null means this is a root-level folder.",
    )
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_folders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resource_folders"
        ordering = ["name"]
        unique_together = ("studio", "parent", "name")

    def __str__(self):
        return self.name


class Resource(models.Model):
    """
    Digital or physical resources (sheet music, recordings, instruments, etc.)
    """

    RESOURCE_TYPE_CHOICES = [
        ("pdf", "PDF Document"),
        ("audio", "Audio File"),
        ("video", "Video File"),
        ("image", "Image"),
        ("physical", "Physical Item"),
        ("link", "External Link"),
        ("sheet_music", "Sheet Music"),
        ("chord_chart", "Chord Chart"),
        ("tablature", "Tablature"),
        ("lyrics", "Lyrics"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="resources")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="uploaded_resources"
    )

    # Band association (optional - if set, resource belongs to specific band)
    band = models.ForeignKey(
        "core.Band",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="resources",
        help_text="If set, this resource belongs to a specific band/group",
    )

    # Resource details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)

    # File information (for digital resources)
    file = models.FileField(
        upload_to="resources/%Y/%m/",
        null=True,
        blank=True,
        help_text="Upload files (PDFs up to 10MB, media files up to 50MB)",
    )
    file_size = models.BigIntegerField(
        null=True, blank=True
    )  # Automatically set if accessed via file property, but useful for caching
    mime_type = models.CharField(max_length=100, blank=True)

    # External link (for link type)
    external_url = models.URLField(blank=True)

    # Organization
    tags = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=100, blank=True)
    folder = models.ForeignKey(
        "ResourceFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
        help_text="Virtual folder this resource belongs to. Null = root level.",
    )

    # Music-specific fields
    instrument = models.CharField(
        max_length=100, blank=True, help_text="Primary instrument (Piano, Guitar, Drums, etc.)"
    )
    composer = models.CharField(max_length=200, blank=True, help_text="Composer/Artist name")
    key_signature = models.CharField(
        max_length=20, blank=True, help_text="Musical key (C, G, Am, etc.)"
    )
    tempo = models.CharField(max_length=50, blank=True, help_text="Tempo marking or BPM")

    # Physical item tracking
    is_physical_item = models.BooleanField(default=False)
    quantity_total = models.IntegerField(default=1)
    quantity_available = models.IntegerField(default=1)

    # Checkout information
    is_lendable = models.BooleanField(default=False)
    checkout_duration_days = models.IntegerField(default=14)

    # Visibility
    is_public = models.BooleanField(default=False)  # Visible to all students
    shared_with_students = models.ManyToManyField(
        Student, blank=True, related_name="shared_resources"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resources"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type"]),
            models.Index(fields=["studio", "is_public"]),
            models.Index(fields=["band"]),
            models.Index(fields=["instrument"]),
            models.Index(fields=["resource_type", "instrument"]),
        ]

    def __str__(self):
        return self.title


class ResourceCheckout(models.Model):
    """
    Track checkout/lending of physical items
    """

    STATUS_CHOICES = [
        ("checked_out", "Checked Out"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
        ("lost", "Lost"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="checkouts")
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="resource_checkouts"
    )

    # Checkout details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="checked_out")
    checked_out_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)

    # Notes
    checkout_notes = models.TextField(blank=True)
    return_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resource_checkouts"
        ordering = ["-checked_out_at"]

    def __str__(self):
        return f"{self.resource.title} - {self.student.user.get_full_name()}"

    @property
    def is_overdue(self):
        """Check if checkout is overdue"""
        if self.status == "returned":
            return False
        return timezone.now().date() > self.due_date


class Setlist(models.Model):
    """
    A collection or "setlist" of resources, like a songbook for a recital.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="setlists")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_setlists"
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    resources = models.ManyToManyField(Resource, through="SetlistResource", related_name="setlists")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resource_setlists"
        ordering = ["-created_at"]
        unique_together = ("studio", "name")

    def __str__(self):
        return self.name


class SetlistResource(models.Model):
    """
    Through model to link Resources to a Setlist, preserving order.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    setlist = models.ForeignKey(Setlist, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        db_table = "resource_setlist_resources"
        ordering = ["order"]
        unique_together = ("setlist", "resource")

    def __str__(self):
        return f"{self.setlist.name} - {self.resource.title} (Order: {self.order})"
