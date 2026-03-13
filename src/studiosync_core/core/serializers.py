from rest_framework import serializers

from .models import Band, Family, SetupStatus, SignedDocument, Student, Studio, Teacher, User


class BandSerializer(serializers.ModelSerializer):
    """Serializer for Band/Group management"""

    members_count = serializers.SerializerMethodField()
    member_details = serializers.SerializerMethodField()
    member_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Student.objects.all(), source="members", required=False
    )
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Band
        fields = [
            "id",
            "name",
            "genre",
            "photo",
            "primary_contact",
            "billing_email",
            "billing_phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "notes",
            "members_count",
            "member_ids",
            "member_details",
        ]

    def get_photo(self, obj):
        """Return relative URL for band photo to work with frontend proxy"""
        if obj.photo:
            return obj.photo.url
        return None

    def get_members_count(self, obj):
        return obj.members.count()

    def get_member_details(self, obj):
        return [
            {
                "id": student.id,
                "full_name": student.user.get_full_name(),
                "instrument": student.instrument,
            }
            for student in obj.members.all()
        ]


class FamilySerializer(serializers.ModelSerializer):
    """Serializer for Family relationships"""

    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = [
            "id",
            "primary_parent",
            "secondary_parent",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "billing_email",
            "students_count",
        ]

    def get_students_count(self, obj):
        return obj.students.count()


class SimpleStudioSerializer(serializers.ModelSerializer):
    cover_image = serializers.ImageField(required=False, allow_null=True)
    logo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Studio
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "website",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "timezone",
            "currency",
            "settings",
            "cover_image",
            "logo",
        ]

    def to_representation(self, instance):
        """Ensure cover_image and logo return relative URLs for frontend proxy"""
        ret = super().to_representation(instance)
        # Prefer direct model fields
        if instance.cover_image:
            ret["cover_image"] = instance.cover_image.url
        elif instance.settings.get("cover_image"):
            ret["cover_image"] = instance.settings["cover_image"]

        if instance.logo:
            ret["logo"] = instance.logo.url
        elif instance.settings.get("logo_url"):
            ret["logo"] = instance.settings["logo_url"]
        return ret


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile management"""

    full_name = serializers.SerializerMethodField()
    student_profile = serializers.SerializerMethodField()
    teacher_profile = serializers.SerializerMethodField()
    studio = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    instrument = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "initials",
            "phone",
            "role",
            "timezone",
            "avatar",
            "preferences",
            "student_profile",
            "teacher_profile",
            "studio",
            "is_active",
            "is_approved",
            "bio",
            "instrument",
        ]
        read_only_fields = ["id", "email", "full_name"]
        extra_kwargs = {
            "bio": {"required": False},
            "instrument": {"required": False},
        }

    def get_avatar(self, obj):
        """Return relative URL for avatar to work with frontend proxy"""
        if obj.avatar:
            return obj.avatar.url
        return None

    def get_bio(self, obj):
        """Return bio from teacher profile if exists, else from preferences for admin"""
        if hasattr(obj, "teacher_profile"):
            return obj.teacher_profile.bio
        if obj.role == "admin" and isinstance(obj.preferences, dict):
            return obj.preferences.get("bio", "")
        return ""

    def get_instrument(self, obj):
        """Return instrument from student profile if exists, else from preferences for admin"""
        if hasattr(obj, "student_profile"):
            return obj.student_profile.instrument
        if obj.role == "admin" and isinstance(obj.preferences, dict):
            return obj.preferences.get("instrument", "")
        return ""

    def to_internal_value(self, data):
        """Handle avatar file upload and profile-specific fields in PATCH/PUT requests"""
        # Create a mutable copy of the data
        if hasattr(data, "dict"):
            mutable_data = data.dict()
            # Django's QueryDict.dict() only returns the *last* value for a key.
            # However, for an uploaded file, the last value is what we want.
            # If we needed list values, we'd use dict(data.lists()).
        else:
            mutable_data = dict(data) if isinstance(data, dict) else data

        avatar_file = None
        if isinstance(mutable_data, dict) and "avatar" in mutable_data:
            avatar_val = mutable_data.get("avatar")
            if isinstance(avatar_val, list) and len(avatar_val) > 0:
                avatar_val = avatar_val[0]
            if hasattr(avatar_val, "read"):
                avatar_file = avatar_val
                mutable_data.pop("avatar", None)

        # Extract profile-specific fields that don't belong on User model
        bio = (
            mutable_data.pop("bio", None)
            if isinstance(mutable_data, dict) and "bio" in mutable_data
            else None
        )
        instrument = (
            mutable_data.pop("instrument", None)
            if isinstance(mutable_data, dict) and "instrument" in mutable_data
            else None
        )

        # Process the rest of the data normally
        internal_value = super().to_internal_value(mutable_data)

        # Add avatar back if it was provided
        if avatar_file:
            internal_value["avatar"] = avatar_file

        # Store profile fields for later use in update()
        if bio is not None:
            internal_value["_bio"] = bio
        if instrument is not None:
            internal_value["_instrument"] = instrument

        return internal_value

    def update(self, instance, validated_data):  # noqa: C901
        # Track approval status for notification
        was_approved = instance.is_approved

        # Extract profile-specific fields
        bio = validated_data.pop("_bio", None)
        instrument = validated_data.pop("_instrument", None)

        # Perform standard update on User model
        instance = super().update(instance, validated_data)

        # Notify user on approval
        if not was_approved and instance.is_approved:
            try:
                from .email_utils import send_account_approved_email
                send_account_approved_email(instance.email, instance.first_name)
            except Exception as e:
                # Don't fail the update if email fails
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send approval email: {e}")

        # Update related profiles if they exist, or save to preferences if admin
        preferences_changed = False
        if bio is not None:
            if hasattr(instance, "teacher_profile"):
                instance.teacher_profile.bio = bio
                instance.teacher_profile.save()
            elif instance.role == "admin":
                if not isinstance(instance.preferences, dict):
                    instance.preferences = {}
                instance.preferences["bio"] = bio
                preferences_changed = True

        if instrument is not None:
            if hasattr(instance, "student_profile"):
                instance.student_profile.instrument = instrument
                instance.student_profile.save()
            elif instance.role == "admin":
                if not isinstance(instance.preferences, dict):
                    instance.preferences = {}
                instance.preferences["instrument"] = instrument
                preferences_changed = True

        if preferences_changed:
            instance.save()

        # Sync is_active to related profiles if changed
        if "is_active" in validated_data:
            is_active = validated_data["is_active"]
            if hasattr(instance, "student_profile"):
                instance.student_profile.is_active = is_active
                instance.student_profile.save()
            if hasattr(instance, "teacher_profile"):
                instance.teacher_profile.is_active = is_active
                instance.teacher_profile.save()

        # Ensure profile exists for the new role
        role = instance.role

        if role == "teacher" and not hasattr(instance, "teacher_profile"):
            from .models import Studio, Teacher

            # Assign to first studio available or owner's studio (fallback logic)
            studio = Studio.objects.first()
            Teacher.objects.create(user=instance, studio=studio)
            # Refresh to ensure teacher_profile is accessible immediately
            instance.refresh_from_db()

        elif role == "student" and not hasattr(instance, "student_profile"):
            from .models import Student, Studio

            studio = Studio.objects.first()
            # Default to active=True or copy user state? Should match logic above, but create assumes Active usually.
            # If user is inactive, maybe student should be too?
            # Let's trust the defaults or subsequent updates.
            Student.objects.create(user=instance, studio=studio, instrument="")
            instance.refresh_from_db()

        return instance

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_student_profile(self, obj):
        if obj.role == "student" and hasattr(obj, "student_profile"):
            student = obj.student_profile
            return {
                "id": student.id,
                "instrument": student.instrument,
                "bands": [{"id": b.id, "name": b.name} for b in student.bands.all()],
                "family_id": student.family_id,
            }
        return None

    def get_teacher_profile(self, obj):
        if obj.role == "teacher" and hasattr(obj, "teacher_profile"):
            teacher = obj.teacher_profile
            return {
                "id": teacher.id,
                "bio": teacher.bio,
                "students_count": teacher.primary_students.count(),
                "studio_id": teacher.studio_id,
            }
        return None

    def get_studio(self, obj):
        # Return studio for owner or teacher
        studio = None
        if hasattr(obj, "owned_studios") and obj.owned_studios.exists():
            studio = obj.owned_studios.first()
        elif obj.role == "teacher" and hasattr(obj, "teacher_profile"):
            studio = obj.teacher_profile.studio

        if studio:
            return SimpleStudioSerializer(studio).data
        return None


class StudioSerializer(serializers.ModelSerializer):
    """Serializer for studio settings"""

    cover_image = serializers.ImageField(required=False, allow_null=True)
    logo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Studio
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "website",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "timezone",
            "currency",
            "settings",
            "cover_image",
            "logo",
        ]
        read_only_fields = ["id", "owner", "subdomain"]

    def update(self, instance, validated_data):
        # Extract fields to see if they changed
        cover_image = validated_data.get('cover_image')
        logo = validated_data.get('logo')

        instance = super().update(instance, validated_data)

        # Sync back to settings for legacy support
        if 'cover_image' in validated_data:
            if instance.cover_image:
                instance.settings['cover_image'] = instance.cover_image.url
            else:
                instance.settings.pop('cover_image', None)
        
        if 'logo' in validated_data:
            if instance.logo:
                instance.settings['logo_url'] = instance.logo.url
            else:
                instance.settings.pop('logo_url', None)
        
        if 'cover_image' in validated_data or 'logo' in validated_data:
            instance.save()
            
        return instance

    def to_representation(self, instance):
        """Ensure cover_image and logo return relative URLs for frontend proxy"""
        ret = super().to_representation(instance)
        # Prefer direct model fields
        if instance.cover_image:
            ret["cover_image"] = instance.cover_image.url
        elif instance.settings.get("cover_image"):
            ret["cover_image"] = instance.settings["cover_image"]

        if instance.logo:
            ret["logo"] = instance.logo.url
        elif instance.settings.get("logo_url"):
            ret["logo"] = instance.settings["logo_url"]
        return ret


class PublicTeacherSerializer(serializers.ModelSerializer):
    """Serializer for public teacher profiles"""

    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = ["id", "first_name", "last_name", "avatar", "bio", "specialties", "instruments"]

    def get_avatar(self, obj):
        """Return relative URL for avatar to work with frontend proxy"""
        if obj.user.avatar:
            return obj.user.avatar.url
        return None


class TeacherSerializer(serializers.ModelSerializer):
    """Full teacher serializer for admin management"""

    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    avatar = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "avatar",
            "bio",
            "specialties",
            "instruments",
            "hourly_rate",
            "availability",
            "auto_accept_bookings",
            "booking_buffer_minutes",
            "is_active",
            "students_count",
        ]

    def get_students_count(self, obj):
        # Count primary students
        return obj.primary_students.count()

    def get_avatar(self, obj):
        if obj.user.avatar:
            return obj.user.avatar.url
        return None


class StudentSerializer(serializers.ModelSerializer):
    """Full student serializer for admin management"""

    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    user = UserSerializer(read_only=True)

    # Allow passing user ID directly for writes
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True, required=False
    )

    primary_teacher = PublicTeacherSerializer(read_only=True)
    primary_teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), source="primary_teacher", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Student
        fields = [
            "id",
            "user",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "instrument",
            "instruments",
            "primary_teacher",
            "primary_teacher_id",
            "enrollment_date",
            "birth_date",
            "total_lessons",
            "last_lesson_date",
            "family",
            "studio",
            "notes",
            "is_active",
            "bands",
        ]


# ============================================================================
# Setup Wizard Serializers
# ============================================================================


class SetupStatusSerializer(serializers.ModelSerializer):
    """Serializer for checking setup completion status"""

    class Meta:
        model = SetupStatus
        fields = ["is_completed", "completed_at", "setup_version", "features_enabled", "setup_data"]
        read_only_fields = ["completed_at"]


class SetupWizardCompleteSerializer(serializers.Serializer):
    """Serializer for completing the entire setup wizard"""

    # Step 1: Language
    language = serializers.CharField(max_length=10, default="en")

    # Step 2: Studio Info
    studio_name = serializers.CharField(max_length=200)
    studio_email = serializers.EmailField()
    studio_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, default="US")
    timezone = serializers.CharField(max_length=50, default="UTC")
    currency = serializers.CharField(max_length=3, default="USD")

    # Step 3: Admin Account
    admin_email = serializers.EmailField()
    admin_first_name = serializers.CharField(max_length=100)
    admin_last_name = serializers.CharField(max_length=100)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    # Step 4: Feature Selection
    billing_enabled = serializers.BooleanField(default=True)
    inventory_enabled = serializers.BooleanField(default=True)
    messaging_enabled = serializers.BooleanField(default=True)
    resources_enabled = serializers.BooleanField(default=True)
    goals_enabled = serializers.BooleanField(default=True)
    bands_enabled = serializers.BooleanField(default=True)
    analytics_enabled = serializers.BooleanField(default=True)
    practice_rooms_enabled = serializers.BooleanField(default=True)

    # Step 5: Quick Settings
    default_lesson_duration = serializers.IntegerField(default=60, min_value=15, max_value=240)
    business_start_hour = serializers.IntegerField(default=9, min_value=0, max_value=23)
    business_end_hour = serializers.IntegerField(default=18, min_value=0, max_value=23)

    # Step: Expanded Business Rules (Billing, Scheduling, Events)
    # Billing
    default_hourly_rate = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=0
    )
    tax_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=0, min_value=0, max_value=100
    )
    charge_tax_on_lessons = serializers.BooleanField(default=False)
    invoice_due_days = serializers.IntegerField(default=14, min_value=0)
    invoice_footer_text = serializers.CharField(required=False, allow_blank=True)

    # Scheduling
    cancellation_notice_period = serializers.IntegerField(
        default=24, min_value=0, help_text="Hours notice required"
    )
    enable_online_booking = serializers.BooleanField(default=False)

    # Events
    default_event_duration = serializers.IntegerField(default=60, min_value=15, max_value=480)

    # Step: Email Settings
    smtp_host = serializers.CharField(max_length=255, required=False, allow_blank=True)
    smtp_port = serializers.IntegerField(default=587)
    smtp_username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    smtp_password = serializers.CharField(max_length=255, required=False, allow_blank=True)
    smtp_from_email = serializers.EmailField(required=False, allow_blank=True)
    smtp_use_tls = serializers.BooleanField(default=True)

    # Step 6: Sample Data
    create_sample_data = serializers.BooleanField(default=False)

    def validate_admin_email(self, value):
        """Ensure admin email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, data):
        """Cross-field validation"""
        # Removed validation for business_end_hour > business_start_hour
        # to support overnight schedules (e.g. 4 PM to 2 AM)
        return data


class SignedDocumentSerializer(serializers.ModelSerializer):
    """Serializer for signed documents"""

    family_name = serializers.ReadOnlyField(source="family.primary_parent.get_full_name")
    signed_by_name = serializers.ReadOnlyField(source="signed_by.get_full_name")

    class Meta:
        model = SignedDocument
        fields = [
            "id",
            "family",
            "family_name",
            "document_type",
            "title",
            "file",
            "signed_by",
            "signed_by_name",
            "signed_at",
            "ip_address",
            "created_at",
        ]
        read_only_fields = ["signed_by", "signed_at", "ip_address", "created_at"]
