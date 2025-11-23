from django.db import models
from django.utils import timezone
import uuid

def generate_tracking_id():
    """Generates a unique tracking ID like PKG-1A2B3C4D"""
    return f"PKG-{str(uuid.uuid4())[:8].upper()}"

class Package(models.Model):
    """
    Represents an package item in the system.
    """
    tracking_id = models.CharField(
        primary_key=True,
        max_length=100, 
        unique=True, 
        default=generate_tracking_id, 
        editable=False
    )
    size = models.IntegerField()
    destination = models.CharField(max_length=200)
    is_fragile = models.BooleanField(default=False, help_text="Handle with care if True")

    def __str__(self):
        return f"{self.tracking_id} (Size: {self.size})"

class StorageBin(models.Model):
    """
    Represents a physical bin in the warehouse.
    Properties: bin_id, capacity, location_code
    """
    bin_id = models.AutoField(primary_key=True)
    location_code = models.CharField(max_length=50, unique=True)
    capacity = models.IntegerField(help_text="Volume capacity of the bin")
    is_occupied = models.BooleanField(default=False)
    current_tracking_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        help_text="Tracking ID of the package currently in this bin"
    )

    class Meta:
        ordering = ['capacity']
        indexes = [
            models.Index(fields=['capacity']),
        ]

    def __str__(self):
        return f"{self.location_code} (ID: {self.bin_id}, Cap: {self.capacity})"

class ShipmentLog(models.Model):
    """
    The Auditor: Immutable log of all actions.
    """
    STATUS_CHOICES = [
        ('INGESTED', 'Ingested on Conveyor'),
        ('STORED', 'Stored in Bin'),
        ('LOADED', 'Loaded on Truck'),
        ('UNLOADED', 'Unloaded from Truck'),
        ('ERROR', 'Error'),
    ]

    tracking_id = models.CharField(max_length=50)
    bin_id = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.tracking_id} - {self.status}"