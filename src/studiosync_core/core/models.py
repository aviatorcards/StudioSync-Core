"""
Core models -User, Studio, Teacher, Student, Family
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from .validators import validate_avatar, validate_image


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_approved", True)
        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        return self.get(email=email)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with role-based access
    Roles: admin, teacher, student, parent
    """

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("teacher", "Teacher"),
        ("student", "Student"),
        ("parent", "Parent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student")
    timezone = models.CharField(max_length=50, default="UTC")
    avatar = models.FileField(
        upload_to="avatars/",
        blank=True,
        null=True,
        validators=[validate_avatar],
        help_text="Profile picture (max 5MB, JPG/PNG/GIF/WebP)",
    )

    # Preferences stored as JSON
    preferences = models.JSONField(default=dict, blank=True)

    # Flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def initials(self):
        return f"{self.first_name[0] if self.first_name else ''}{self.last_name[0] if self.last_name else ''}".upper()

    def natural_key(self):
        return (self.email,)
    natural_key.fget = lambda self: (self.email,)

    def wants_notification(self, notification_type_internal, channel="push"):
        """
        Check if user wants a specific notification type via a specific channel.
        channel: 'push', 'email', 'sms'
        """
        # Map internal types to UI preference keys
        TYPE_MAPPING = {
            "lesson_scheduled": "lesson_reminders",
            "lesson_reminder": "lesson_reminders",
            "lesson_cancelled": "lesson_reminders",
            "new_message": "new_messages",
            "payment_received": "payment_alerts",
            "payment_due": "payment_alerts",
            "new_student": "student_updates",
            "student_goal_reached": "student_updates",
        }
        
        pref_key = TYPE_MAPPING.get(notification_type_internal, notification_type_internal)
        notif_prefs = self.preferences.get("notifications", {})
        
        # Check channel master switch
        if channel == "push" and not notif_prefs.get("push_enabled", True):
            return False
        if channel == "email" and not notif_prefs.get("email_enabled", True):
            return False
        if channel == "sms" and not notif_prefs.get("sms_enabled", False):
            return False
            
        # Check specific type switch (default to True if not explicitly set)
        return notif_prefs.get(pref_key, True)


class Studio(models.Model):
    """
    Represents a music studio/school
    Supports multi-tenancy if needed
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subdomain = models.SlugField(unique=True, blank=True, null=True)

    # Owner/admin
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_studios")

    # Contact information
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)

    # Address
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="US")

    # Settings
    timezone = models.CharField(max_length=50, default="UTC")
    currency = models.CharField(max_length=3, default="USD")
    settings = models.JSONField(default=dict, blank=True)

    # Visual Layout
    cover_image = models.ImageField(
        upload_to="studio_covers/",
        blank=True,
        null=True,
        validators=[validate_image],
        help_text="Studio cover image (max 5MB, JPG/PNG/GIF/WebP)",
    )
    logo = models.ImageField(
        upload_to="studio_logos/",
        blank=True,
        null=True,
        validators=[validate_image],
        help_text="Studio logo (max 5MB, JPG/PNG/GIF/WebP)",
    )
    layout_data = models.JSONField(default=dict, blank=True)

    # Flags
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "studios"
        ordering = ["name"]

    def __str__(self):
        return self.name


    def natural_key(self):
        return (self.name,)
    natural_key.fget = lambda self: (self.name,)


class Teacher(models.Model):
    """
    Teacher profile linked to a User
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="teachers")

    # Professional info
    bio = models.TextField(blank=True)
    specialties = models.JSONField(default=list, blank=True)  # e.g., ["Piano", "Vocal"]
    instruments = models.JSONField(default=list, blank=True)

    # Rates and scheduling
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.JSONField(default=dict, blank=True)  # Weekly schedule

    # Settings
    auto_accept_bookings = models.BooleanField(default=False)
    booking_buffer_minutes = models.IntegerField(default=0)  # Time between lessons

    # Flags
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teachers"
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.studio.name}"


class Family(models.Model):
    """
    Represents a family unit (parents + children)
    Used for group billing and communication
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="families")

    # Parents
    primary_parent = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="primary_parent_families"
    )
    secondary_parent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_parent_families",
    )

    # Shared info (can override individual student info)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    # Billing
    billing_email = models.EmailField(blank=True)  # Defaults to primary_parent.email

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "families"
        verbose_name_plural = "Families"

    def __str__(self):
        return f"Family of {self.primary_parent.last_name}"


class BandManager(models.Manager):
    def get_by_natural_key(self, studio_natural_key, name):
        studio = Studio.objects.get_by_natural_key(*studio_natural_key)
        return self.get(studio=studio, name=name)


class Band(models.Model):
    """
    Represents a band/group for billing purposes
    Can be used for actual bands or groups of students
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="bands")

    # Primary contact (usually band leader or manager)
    primary_contact = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="primary_contact_for_bands"
    )

    # Band name
    name = models.CharField(max_length=200, blank=True)

    # Genre
    genre = models.CharField(max_length=100, blank=True)

    # Visual identity
    photo = models.ImageField(
        upload_to="bands/",
        blank=True,
        null=True,
        validators=[validate_image],
        help_text="Band/group photo (max 5MB, JPG/PNG/GIF/WebP)",
    )

    # Billing information
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20, blank=True)

    # Address
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="US")

    # Notes
    notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BandManager()

    class Meta:
        db_table = "bands"
        verbose_name_plural = "Bands"
        ordering = ["name", "primary_contact__last_name"]

    def __str__(self):
        if self.name:
            return self.name
        if self.primary_contact:
            return f"{self.primary_contact.get_full_name()} Band"
        return f"Band {self.id}"

    def natural_key(self):
        return (self.studio.natural_key(), self.name)
    natural_key.fget = lambda self: (self.studio.natural_key(), self.name)


class Student(models.Model):
    """
    Student profile linked to a User
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="students")
    family = models.ForeignKey(
        Family, on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    bands = models.ManyToManyField(Band, blank=True, related_name="members")

    # Primary teacher (optional - students can have multiple teachers via lessons)
    primary_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name="primary_students"
    )

    # Musical information
    instrument = models.CharField(max_length=100, blank=True)
    instruments = models.JSONField(default=list, blank=True)

    goals_description = models.TextField(
        blank=True
    )  # Renamed to avoid conflict with StudentGoal.goals

    # Important dates
    enrollment_date = models.DateField(default=timezone.now)
    birth_date = models.DateField(null=True, blank=True)

    # Medical/emergency information
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    medical_notes = models.TextField(blank=True)

    # Progress tracking
    total_lessons = models.IntegerField(default=0)
    last_lesson_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    # Flags
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "students"
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.instrument}"


class SignedDocument(models.Model):
    """
    Stores digitally signed documents (waivers, policies, etc.)
    Includes audit trail for security/validity
    """

    DOCUMENT_TYPES = [
        ("liability_waiver", "Liability Waiver"),
        ("media_release", "Media Release"),
        ("policy_agreement", "Studio Policy Agreement"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name="signed_documents")

    # Signer links (can be Student or Family/Parent)
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="signed_documents"
    )
    family = models.ForeignKey(
        Family, on_delete=models.SET_NULL, null=True, blank=True, related_name="signed_documents"
    )
    signer_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="signatures"
    )

    # Document details
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    content_snapshot = models.TextField(help_text="Copy of the text agreed to")

    # Signature Data
    signature_image = models.FileField(upload_to="signatures/")

    # Audit Trail
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "signed_documents"
        ordering = ["-signed_at"]

    def __str__(self):
        signer = self.signer_user.get_full_name() if self.signer_user else "Unknown"
        return f"{self.get_document_type_display()} - {signer}"


class SetupStatus(models.Model):
    """Tracks whether initial setup wizard has been completed"""

    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    setup_version = models.CharField(max_length=10, default="1.0")

    # Store feature selections and other setup data
    features_enabled = models.JSONField(default=dict, blank=True)
    setup_data = models.JSONField(
        default=dict, blank=True, help_text="Additional setup configuration"
    )

    class Meta:
        db_table = "setup_status"
        verbose_name_plural = "Setup Status"

    def __str__(self):
        status = "Completed" if self.is_completed else "Pending"
        return f"Setup Status: {status}"

    @classmethod
    def is_setup_complete(cls):
        """Check if setup has been completed"""
        setup = cls.objects.first()
        return setup and setup.is_completed

    def mark_complete(self):
        """Mark setup as completed"""
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save()
