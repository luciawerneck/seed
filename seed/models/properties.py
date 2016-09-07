# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2016, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""
from __future__ import unicode_literals

import logging

from django.db import models
from django_pgjson.fields import JsonField

from seed.data_importer.models import ImportFile
from seed.lib.superperms.orgs.models import Organization
from seed.models import (
    COMPOSITE_BS, ASSESSED_RAW, PORTFOLIO_RAW, GREEN_BUTTON_RAW
)
from seed.utils.generic import split_model_fields, obj_to_dict

logger = logging.getLogger(__name__)

# State of the data that was imported. This will be used to flag which
# rows are orphaned and can be deleted.

# TODO: There are a bunch of these states already defined in the data_importer/
# models.py file. Should probably revert this and use those.
DATA_STATE_UNKNOWN = 0
DATA_STATE_IMPORT = 1
DATA_STATE_MAPPING = 2
DATA_STATE_MATCHING = 3
DATA_STATE = (
    (DATA_STATE_UNKNOWN, 'Unknown'),
    (DATA_STATE_IMPORT, 'Post Import'),
    (DATA_STATE_MAPPING, 'Post Mapping'),
    (DATA_STATE_MATCHING, 'Post Matching'),
)
from django.db.models.fields.related import ManyToManyField
from seed.models import Cycle
from seed.models import StatusLabel
from auditlog import AUDIT_IMPORT
from auditlog import DATA_UPDATE_TYPE
from seed.utils.time import convert_datestr

# Oops! we override a builtin in some of the models
property_decorator = property


class Property(models.Model):
    """The canonical property"""
    organization = models.ForeignKey(Organization)

    # Handle properties that may have multiple properties (e.g. buildings)
    campus = models.BooleanField(default=False)
    parent_property = models.ForeignKey('Property', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'properties'

    def __unicode__(self):
        return u'Property - %s' % (self.pk)


class PropertyState(models.Model):
    """Store a single property"""
    # import_record = models.ForeignKey(ImportRecord)
    # Support finding the property by the import_file and source_type
    import_file = models.ForeignKey(ImportFile, null=True, blank=True)
    # FIXME: source_type needs to be a foreign key or make it import_file.source_type
    source_type = models.IntegerField(null=True, blank=True, db_index=True)
    super_organization = models.ForeignKey(Organization, blank=True, null=True)
    data_state = models.IntegerField(choices=DATA_STATE, default=0)

    # Is this still being used during matching? Apparently so.
    confidence = models.FloatField(default=0, null=True, blank=True)

    # TODO: hmm, name this jurisdiction_property_id to stay consistent?
    jurisdiction_property_identifier = models.CharField(max_length=255,
                                                        null=True, blank=True)

    custom_id_1 = models.CharField(max_length=255, null=True, blank=True)

    # If the property is a campus then the pm_parent_property_id is the same
    # for all the properties. The master campus record (campus=True) the
    # pm_property_id will be set the same as pm_parent_property_id
    pm_parent_property_id = models.CharField(max_length=255, null=True, blank=True)
    pm_property_id = models.CharField(max_length=255, null=True, blank=True)
    building_portfolio_manager_identifier = models.CharField(max_length=255, null=True, blank=True)
    building_home_energy_score_identifier = models.CharField(max_length=255, null=True, blank=True)

    # Tax Lot Number of the property
    lot_number = models.CharField(max_length=255, null=True, blank=True)
    property_name = models.CharField(max_length=255, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=255, null=True, blank=True)

    # Only spot where it's 'building' in the app, b/c this is a PortMgr field.
    building_count = models.IntegerField(null=True, blank=True)

    property_notes = models.TextField(null=True, blank=True)
    year_ending = models.DateField(null=True, blank=True)

    # Tax IDs are often stuck here.
    use_description = models.CharField(max_length=255, null=True, blank=True)

    gross_floor_area = models.FloatField(null=True, blank=True)
    year_built = models.IntegerField(null=True, blank=True)
    recent_sale_date = models.DateTimeField(null=True, blank=True)
    conditioned_floor_area = models.FloatField(null=True, blank=True)
    occupied_floor_area = models.FloatField(null=True, blank=True)
    owner = models.CharField(max_length=255, null=True, blank=True)
    owner_email = models.CharField(max_length=255, null=True, blank=True)
    owner_telephone = models.CharField(max_length=255, null=True, blank=True)
    owner_address = models.CharField(max_length=255, null=True, blank=True)
    owner_city_state = models.CharField(max_length=255, null=True, blank=True)
    owner_postal_code = models.CharField(max_length=255, null=True, blank=True)

    energy_score = models.IntegerField(null=True, blank=True)
    site_eui = models.FloatField(null=True, blank=True)
    generation_date = models.DateTimeField(null=True, blank=True)
    release_date = models.DateTimeField(null=True, blank=True)
    source_eui_weather_normalized = models.FloatField(null=True, blank=True)
    site_eui_weather_normalized = models.FloatField(null=True, blank=True)
    source_eui = models.FloatField(null=True, blank=True)
    energy_alerts = models.TextField(null=True, blank=True)
    space_alerts = models.TextField(null=True, blank=True)
    building_certification = models.CharField(max_length=255, null=True,
                                              blank=True)

    extra_data = JsonField(default={}, blank=True)

    def promote(self, cycle):
        """
        Promote the PropertyState to the view table for the given cycle

        Args:
            cycle: Cycle to assign the view

        Returns:
            The resulting PropertyView (note that it is not returning the
            PropertyState)

        """

        # First check if the cycle and the PropertyState already have a view
        pvs = PropertyView.objects.filter(cycle=cycle, state=self)

        if len(pvs) == 0:
            logger.debug("Found 0 PropertyViews, adding property, promoting")
            # There are no PropertyViews for this property state and cycle.
            # Most likely there is nothing to match right now, so just
            # promote it to the view

            # Need to create a property for this state
            prop = Property.objects.create(
                organization=self.super_organization
            )

            pv = PropertyView.objects.create(property=prop, cycle=cycle,
                                             state=self)

            return pv
        elif len(pvs) == 1:
            logger.debug("Found 1 PropertyView... Nothing to do")
            # PropertyView already exists for cycle and state. Nothing to do.

            return pvs[0]
        else:
            logger.debug("Found %s PropertyView" % len(pvs))
            logger.debug("This should never occur, famous last words?")

            return None

    def __unicode__(self):
        return u'Property State - %s' % (self.pk)

    # TODO: deprecate this method, was hacked during mapping testing
    def assign_cycle_and_tax_lot(self, org, start_date, end_date, tax_lot_id):
        """

        Args:
            org: Organization object
            start_date: Start date of the property cycle
            end_date: End date of the property cycle
            tax_lot_id: Tax lot id

        Returns:

        """

        # # TODO: we should set the cycle before we iterate over *every* row
        # cycle, _ = Cycle.objects.get_or_create(
        #     name=u'Hack Cycle',
        #     organization=org,
        #     start=start_date,
        #     end=end_date
        # )
        #
        # # create 1 to 1 pointless taxlots for now
        # # tl = TaxLot.objects.create(
        # #     organization=org
        # # )
        # #
        # # tls, _ = TaxLotState.objects.get_or_create(
        # #     jurisdiction_taxlot_identifier=tax_lot_id
        # # )
        # #
        # # tlv, _ = TaxLotView.objects.get_or_create(
        # #     taxlot=tl,
        # #     state=tls,
        # #     cycle=cycle,
        # # )
        #
        # self.save()
        #
        # # set the property view here for now to make sure that the data
        # # show up in the bluesky tables
        # property = Property.objects.create(
        #     organization=org
        # )
        #
        # PropertyView.objects.get_or_create(
        #     property=property,
        #     cycle=cycle,
        #     state=self
        # )

        return self

    def clean(self, *args, **kwargs):
        date_field_names = (
            'year_ending',
            'generation_date',
            'release_date',
            'recent_sale_date'
        )

        # TODO: Where to put in the custom_id_1
        # custom_id_1 = getattr(self, 'custom_id_1')
        # if isinstance(custom_id_1, unicode):
        #     custom_id_1 = unicodedata.normalize('NFKD', custom_id_1).encode(
        #         'ascii', 'ignore'
        #     )
        # if custom_id_1 and len(str(custom_id_1)) > 128:
        #     self.custom_id_1 = custom_id_1[:128]
        for field in date_field_names:
            value = getattr(self, field)
            if value and isinstance(value, basestring):
                setattr(self, field, convert_datestr(value))

    def to_dict(self, fields=None, include_related_data=True):
        """
        Returns a dict version of the PropertyState, either with all fields
        or masked to just those requested.
        """
        if fields:
            model_fields, ed_fields = split_model_fields(self, fields)
            extra_data = self.extra_data
            ed_fields = filter(lambda f: f in extra_data, ed_fields)

            result = {
                field: getattr(self, field) for field in model_fields
            }
            result['extra_data'] = {
                field: extra_data[field] for field in ed_fields
            }

            # always return id's and canonical_building id's
            result['id'] = result['pk'] = self.pk

            # TODO: I don't think this is needed anymore
            result['canonical_building'] = (
                self.canonical_building and self.canonical_building.pk
            )

            # should probably also return children, parents, and coparent
            # result['children'] = map(lambda c: c.id, self.children.all())
            # result['parents'] = map(lambda p: p.id, self.parents.all())
            # result['co_parent'] = (self.co_parent and self.co_parent.pk)
            # result['coparent'] = (self.co_parent and {
            #     field: self.co_parent.pk for field in ['pk', 'id']
            #     })

            return result

        d = obj_to_dict(self, include_m2m=include_related_data)

        # if include_related_data:
        # d['parents'] = list(self.parents.values_list('id', flat=True))
        # d['co_parent'] = self.co_parent.pk if self.co_parent else None

        return d

    # TODO: oops, this should be in the ImportFile world, not the property
    @staticmethod
    def find_unmatched(import_file):
        """Get unmatched building snapshots' id info from an import file.

        :param import_file: ImportFile inst.
        :rtype: list of tuples, field values specified in BS_VALUES_LIST.

        NB: This does not return a queryset!

        """

        return PropertyState.objects.filter(
            ~models.Q(source_type__in=[
                COMPOSITE_BS, ASSESSED_RAW, PORTFOLIO_RAW, GREEN_BUTTON_RAW
            ]),
            # match_type=None,
            import_file=import_file,
            # canonical_building=None, # I assume that this was causing the "unmatched building to be defined"
        )


class PropertyView(models.Model):
    """Similar to the old world of canonical building"""
    property = models.ForeignKey(Property,
                                 related_name='views')  # different property views can be associated with each other (2012, 2013).
    cycle = models.ForeignKey(Cycle)
    state = models.ForeignKey(PropertyState)

    labels = ManyToManyField(StatusLabel)

    def __unicode__(self):
        return u'Property View - %s' % (self.pk)

    class Meta:
        unique_together = ('property', 'cycle',)

    def __init__(self, *args, **kwargs):
        self._import_filename = kwargs.pop('import_filename', None)
        super(PropertyView, self).__init__(*args, **kwargs)

    def initialize_audit_logs(self, **kwargs):
        kwargs.update({
            'organization': self.property.organization,
            'state': self.state,
            'view': self,
            'record_type': AUDIT_IMPORT
        })
        return PropertyAuditLog.objects.create(**kwargs)

    def update_state(self, new_state, **kwds):
        view_audit_log = PropertyAuditLog.objects.filter(
            state=self.state
        ).first()
        if not view_audit_log:
            view_audit_log = self.initialize_audit_logs(
                description="Initial audit log added on update.",
                record_type=AUDIT_IMPORT,
            )
        new_audit_log = PropertyAuditLog(
            organization=self.property.organization,
            parent1=view_audit_log,
            state=new_state,
            view=self,
            **kwds
        )
        self.state = new_state
        self.save()
        new_audit_log.save()
        return

    def save(self, *args, **kwargs):
        # create audit log on creation
        audit_log_initialized = True if self.id else False
        import_filename = kwargs.pop('import_filename', self._import_filename)
        super(PropertyView, self).save(*args, **kwargs)
        if not audit_log_initialized:
            self.initialize_audit_logs(
                description="Initial audit log added on creation/save.",
                record_type=AUDIT_IMPORT,
                import_filename=import_filename
            )

    @property_decorator
    def import_filename(self):
        """Get the import file name form the audit logs"""
        if not getattr(self, '_import_filename', None):
            audit_log = PropertyAuditLog.objects.filter(
                view_id=self.pk).order_by('created').first()
            self._import_filename = audit_log.import_filename
        return self._import_filename


class PropertyAuditLog(models.Model):
    organization = models.ForeignKey(Organization)
    parent1 = models.ForeignKey('PropertyAuditLog', blank=True, null=True,
                                related_name='propertyauditlog__parent1')
    parent2 = models.ForeignKey('PropertyAuditLog', blank=True, null=True,
                                related_name='propertyauditlog__parent2')

    state = models.ForeignKey('PropertyState',
                              related_name='propertyauditlog__state')
    view = models.ForeignKey('PropertyView',
                             related_name='propertyauditlog__view', null=True)

    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    import_filename = models.CharField(max_length=255, null=True, blank=True)
    record_type = models.IntegerField(choices=DATA_UPDATE_TYPE, null=True,
                                      blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
