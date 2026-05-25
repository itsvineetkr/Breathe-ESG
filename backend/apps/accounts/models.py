"""
accounts/models.py

Design decision: We do NOT extend or replace Django's built-in User model.
Reason: Swapping AUTH_USER_MODEL mid-project is painful and error-prone.
Instead, we create a thin UserProfile mapping each User to an Organization + Role.
This also makes it easy to add SSO (SAML/OAuth) later — just create the profile on first login.

Multi-tenancy: Every query in this system is filtered by request.user.profile.organization.
Organization is the root of the data isolation tree.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Organization(models.Model):
    """
    Root tenant. One organization = one enterprise client.

    electricity_emission_factor: kg CO2e per kWh. Varies by country/grid.
    Default 0.233 is the IEA 2023 world average. In production, this would be
    set per organization based on their grid region (UK: 0.207, US avg: 0.386, etc.)

    plant_code_map: SAP plant codes are opaque (e.g. "WERK01"). Without a lookup,
    we can't tell if WERK01 is in Berlin or Mumbai. Orgs upload this mapping once.

    field_mapping_overrides: Allows orgs to configure custom header → field mappings
    for their specific SAP configuration (German vs English headers, custom column names).
    Structure: {"SAP": {"Menge": "quantity", "Werk": "plant_code"}, "UTILITY": {...}}
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)

    # Configurable emission factor for Scope 2 (varies by electrical grid)
    electricity_emission_factor = models.FloatField(
        default=0.233,
        help_text="kg CO2e per kWh. Default: IEA 2023 world average (0.233)."
    )

    # SAP plant code → human-readable name mapping
    # e.g. {"WERK01": "Berlin Plant", "WERK02": "Munich Warehouse"}
    plant_code_map = models.JSONField(
        default=dict,
        help_text="SAP plant code to human-readable location name."
    )

    # Per-org field mapping overrides for each source type
    # e.g. {"SAP": {"Menge": "quantity"}, "UTILITY": {"kWh Used": "usage_kwh"}}
    field_mapping_overrides = models.JSONField(
        default=dict,
        help_text="Custom header→field mappings per source type."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class UserProfile(models.Model):
    """
    Maps a Django User → Organization + Role.

    Roles:
    - admin: Can upload data, manage analysts, view audit logs, manage org settings.
    - analyst: Can review records, approve/reject, add notes. Cannot manage users.

    The first user to register an organization gets admin role automatically.
    Admins can add analysts by email; the system creates a Django User + Profile.
    """

    ROLE_ADMIN = 'admin'
    ROLE_ANALYST = 'analyst'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_ANALYST, 'Analyst'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='members'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} ({self.role}) @ {self.organization.name}"

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    class Meta:
        ordering = ['organization', 'role', 'user__email']
