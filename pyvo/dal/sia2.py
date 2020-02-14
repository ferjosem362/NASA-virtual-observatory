# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
A module for searching for images in a remote archive.

A Simple Image Access (SIA) service allows a client to search for
images based on a number of criteria/parameters. The results are
represented in `pyvo.dam.obscore.ObsCoreMetadata` format.

The ``SIAService`` class can represent a specific service available at a URL
endpoint.
"""

from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy import time

from .query import DALResults, DALQuery, DALService, Record
from .adhoc import DatalinkResultsMixin, AxisParamMixin, SodaRecordMixin,\
    DatalinkRecordMixin
from .params import IntervalQueryParam, StrQueryParam, EnumQueryParam
from .vosi import AvailabilityMixin, CapabilityMixin
from ..dam import ObsCoreMetadata


__all__ = ["search", "SIAService", "SIAQuery", "SIAResults", "ObsCoreRecord"]

SIA2_STANDARD_ID = 'ivo://ivoa.net/std/SIA#query-2.0'

# to be moved to ObsCore
POLARIZATION_STATES = ['I', 'Q', 'U', 'V', 'RR', 'LL', 'RL', 'LR',
                       'XX', 'YY', 'XY', 'YX', 'POLI', 'POLA']
CALIBRATION_LEVELS = [0, 1, 2, 3, 4]

SIA_PARAMETERS_DESC =\
    """     pos : single or list of tuples
              angle units (default: deg)
            the positional region(s) to be searched for data. Each region can
            be expressed as a tuple representing a CIRCLE, RANGE or POLYGON as
            follows:
            (ra, dec, radius) - for CIRCLE. (angle units - defaults to)
            (long1, long2, lat1, lat2) - for RANGE (angle units required)
            (ra, dec, ra, dec, ra, dec ... ) ra/dec points for POLYGON all
            in angle units
        band : scalar, tuple(interval) or list of tuples
            (spectral units (default: meter)
            the energy interval(s) to be searched for data.
        time: single or list of `~astropy.time.Time` or compatible strings
            the time interval(s) to be searched for data.
        pol: single or list of str from `pyvo.dam.obscore.POLARIZATION_STATES`
            the polarization state(s) to be searched for data.
        field_of_view: single or list of tuples
            angle units (default arcsec)
            the range(s) of field of view (size) to be searched for data
        spatial_resolution: single or list of tuples
            angle units required
            the range(s) of spatial resolution to be searched for data
        spectral_resolving_power: single or list of tuples
            the range(s) of spectral resolving power to be searched for data
        exptime: single or list of tuples
            time units (default: second)
            the range(s) of exposure times to be searched for data
        timeres: single of list of tuples
            time units (default: second)
            the range(s) of temporal resolution to be searched for data
        global_id: single or list of str
            specifies the unique identifier of dataset(s). It is global because
            it must include information regarding the publisher
            (obs_publisher_did in ObsCore)
        collection: single or list of str
            name of the collection that the data belongs to
        facility: single or list of str
            specifies the name of the facility (usually telescope) where
            the data was acquired.
        instrument: single or list of str
            specifies the name of the instrument with which the data was
            acquired.
        data_type: 'image'|'cube'
            specifies the type of the data
        calib_level: single or list from enum
            `pyvo.dam.obscore.CALIBRATION_LEVELS`
            specifies the calibration level of the data. Can be a single value
            or a list of values
        target_name: single or list of str
            specifies the name of the target (e.g. the intention of the
            original science program or observation)
        res_format : single or list of strings
            specifies response format(s).
        max_records: int
            allows the client to limit the number or records in the response"""


def search(url, pos=None, band=None, time=None, pol=None,
           field_of_view=None, spatial_resolution=None,
           spectral_resolving_power=None, exptime=None,
           timeres=None, global_id=None, facility=None, collection=None,
           instrument=None, data_type=None, calib_level=None,
           target_name=None, res_format=None, maxrec=None, session=None):
    """
    submit a simple SIA query to a SIAv2 compatible service

        PARAMETERS
        ----------

        url - url of the SIA service (base or endpoint)
        _SIA2_PARAMETERS

    """
    service = SIAService(url)
    return service.search(pos=pos, band=band, time=time, pol=pol,
                          field_of_view=field_of_view,
                          spatial_resolution=spatial_resolution,
                          spectral_resolving_power=spectral_resolving_power,
                          exptime=exptime, timeres=timeres,
                          global_id=global_id,
                          facility=facility, collection=collection,
                          instrument=instrument, data_type=data_type,
                          calib_level=calib_level, target_name=target_name,
                          res_format=res_format, maxrec=maxrec,
                          session=session)


search.__doc__ = search.__doc__.replace('_SIA2_PARAMETERS',
                                        SIA_PARAMETERS_DESC)


def _tolist(value):
    # return value as a list - is there something in Python to do that?
    if not value:
        return []
    if isinstance(value, list):
        return value
    return [value]


class SIAService(DALService, AvailabilityMixin, CapabilityMixin):
    """
    a representation of an SIA2 service
    """

    def __init__(self, baseurl, session=None):
        """
        instantiate an SIA service

        Parameters
        ----------
        url : str
           url - URL of the SIA service (base or query endpoint)
        session : object
           optional session to use for network requests
        """

        super().__init__(baseurl, session=session)

        # Check if the session has an update_from_capabilities attribute.
        # This means that the session is aware of IVOA capabilities,
        # and can use this information in processing network requests.
        # One such usecase for this is auth.
        if hasattr(self._session, 'update_from_capabilities'):
            self._session.update_from_capabilities(self.capabilities)

        self.query_ep = None  # service query end point
        for cap in self.capabilities:
            # assumes that the access URL is the same regardless of the
            # authentication method except BasicAA which is not supported
            # in pyvo. So pick any access url as long as it's not
            if cap.standardid == SIA2_STANDARD_ID:
                for interface in cap.interfaces:
                    if interface.accessurls and not \
                        [m for m in interface.securitymethods if
                         m.standardid != 'ivo://ivoa.net/sso#BasicAA']:
                        self.query_ep = interface.accessurls[0].content
                        break

    def search(self, pos=None, band=None, time=None, pol=None,
               field_of_view=None, spatial_resolution=None,
               spectral_resolving_power=None, exptime=None,
               timeres=None, global_id=None, facility=None, collection=None,
               instrument=None, data_type=None, calib_level=None,
               target_name=None, res_format=None, maxrec=None, session=None):
        """
        Performs a SIAv2 search against a SIAv2 service

        See Also
        --------
        pyvo.dal.sia2.SIAQuery

        """
        return SIAQuery(self.query_ep, pos=pos, band=band,
                        time=time, pol=pol,
                        field_of_view=field_of_view,
                        spatial_resolution=spatial_resolution,
                        spectral_resolving_power=spectral_resolving_power,
                        exptime=exptime, timeres=timeres,
                        global_id=global_id,
                        facility=facility, collection=collection,
                        instrument=instrument, data_type=data_type,
                        calib_level=calib_level, target_name=target_name,
                        res_format=res_format, maxrec=maxrec,
                        session=session).execute()


class SIAQuery(DALQuery, AxisParamMixin):
    """
    a class very similar to :py:attr:`~pyvo.dal.query.SIAQuery` class but
    used to interact with SIAv2 services.
    """

    def __init__(self, url, pos=None, band=None, time=None, pol=None,
                 field_of_view=None, spatial_resolution=None,
                 spectral_resolving_power=None, exptime=None,
                 timeres=None, global_id=None,
                 facility=None, collection=None,
                 instrument=None, data_type=None, calib_level=None,
                 target_name=None, res_format=None, maxrec=None,
                 session=None):
        """
        initialize the query object with a url and the given parameters

        Note: The majority of the attributes represent constraints used to
        query the SIA service and are represented through lists. Multiple value
        attributes are OR-ed in the query, however the values of different
        attributes are AND-ed. Intervals are represented with tuples and
        open-ended intervals should be expressed with float("-inf") or
        float("inf"). Eg. For all values less than or equal to 600 use
        (float(-inf), 600)

        Additional attribute constraints can be specified (or removed) after
        this object has been created using the *.add and *_del methods.

        Parameters
        ----------
        url : url where to send the query request to
        _SIA2_PARAMETERS
        session : object
           optional session to use for network requests

        Returns
        -------
        SIAResults
            a container holding a table of matching image records. Records are
            represented in IVOA ObsCore format

        Raises
        ------
        DALServiceError
            for errors connecting to or communicating with the service
        DALQueryError
            if the service responds with an error,
            including a query syntax error.

        See Also
        --------
        SIAResults
        pyvo.dal.query.DALServiceError
        pyvo.dal.query.DALQueryError

        """
        super().__init__(url, session=session)

        for pp in _tolist(pos):
            self.pos.add(pp)

        for bb in _tolist(band):
            self.band.add(bb)

        for tt in _tolist(time):
            self.time.add(tt)

        for pp in _tolist(pol):
            self.pol.add(pp)

        for ff in _tolist(field_of_view):
            self.field_of_view.add(ff)

        for sp in _tolist(spatial_resolution):
            self.spatial_resolution.add(sp)

        for sr in _tolist(spectral_resolving_power):
            self.spectral_resolving_power.add(sr)

        for et in _tolist(exptime):
            self.exptime.add(et)

        for tr in _tolist(timeres):
            self.timeres.add(tr)

        for ii in _tolist(global_id):
            self.global_id.add(ii)

        for ff in _tolist(facility):
            self.facility.add(ff)

        for col in _tolist(collection):
            self.collection.add(col)

        for inst in _tolist(instrument):
            self.instrument.add(inst)

        for dt in _tolist(data_type):
            self.data_type.add(dt)

        for cal in _tolist(calib_level):
            self.calib_level.add(cal)

        for tt in _tolist(target_name):
            self.target_name.add(tt)

        for rf in _tolist(res_format):
            self.res_format.add(rf)

        self.maxrec = maxrec

    __init__.__doc__ = \
        __init__.__doc__.replace('_SIA2_PARAMETERS', SIA_PARAMETERS_DESC)

    @property
    def field_of_view(self):
        if not hasattr(self, '_fov'):
            self._fov = IntervalQueryParam(u.deg)
            self['FOV'] = self._fov.dal
        return self._fov

    @property
    def spatial_resolution(self):
        if not hasattr(self, '_spatres'):
            self._spatres = IntervalQueryParam(u.arcsec)
            self['SPATRES'] = self._spatres.dal
        return self._spatres

    @property
    def spectral_resolving_power(self):
        if not hasattr(self, '_specrp'):
            self._specrp = IntervalQueryParam()
            self['SPECRP'] = self._specrp.dal
        return self._specrp

    @property
    def exptime(self):
        if not hasattr(self, '_exptime'):
            self._exptime = IntervalQueryParam(u.second)
            self['EXPTIME'] = self._exptime.dal
        return self._exptime

    @property
    def timeres(self):
        if not hasattr(self, '_timeres'):
            self._timeres = IntervalQueryParam(u.second)
            self['TIMERES'] = self._timeres.dal
        return self._timeres

    @property
    def global_id(self):
        if not hasattr(self, '_global_id'):
            self._global_id = StrQueryParam()
            self['ID'] = self._global_id.dal
        return self._global_id

    @property
    def facility(self):
        if not hasattr(self, '_facility'):
            self._facility = StrQueryParam()
            self['FACILITY'] = self._facility.dal
        return self._facility

    @property
    def collection(self):
        if not hasattr(self, '_collection'):
            self._collection = StrQueryParam()
            self['COLLECTION'] = self._collection.dal
        return self._collection

    @property
    def instrument(self):
        if not hasattr(self, '_instrument'):
            self._instrument = StrQueryParam()
            self['INSTRUMENT'] = self._instrument.dal
        return self._instrument

    @property
    def data_type(self):
        if not hasattr(self, '_data_type'):
            self._data_type = StrQueryParam()
            self['DPTYPE'] = self._data_type.dal
        return self._data_type

    @property
    def calib_level(self):
        if not hasattr(self, '_cal'):
            self._cal = EnumQueryParam(CALIBRATION_LEVELS)
            self['CALIB'] = self._cal.dal
        return self._cal

    @property
    def target_name(self):
        if not hasattr(self, '_target'):
            self._target_name = StrQueryParam()
            self['TARGET'] = self._target_name.dal
        return self._target_name

    @property
    def res_format(self):
        if not hasattr(self, '_res_format'):
            self._res_format = StrQueryParam()
            self['FORMAT'] = self._res_format.dal
        return self._res_format

    @property
    def maxrec(self):
        return self._maxrec

    @maxrec.setter
    def maxrec(self, val):
        if not val:
            return
        if not isinstance(val, int) and val > 0:
            raise ValueError('maxrec {} must be positive int'.format(val))
        self._maxrec = val
        self['MAXREC'] = str(val)

    def execute(self):
        """
        submit the query and return the results as a SIAResults instance

        Raises
        ------
        DALServiceError
           for errors connecting to or communicating with the service
        DALQueryError
           for errors either in the input query syntax or
           other user errors detected by the service
        DALFormatError
           for errors parsing the VOTable response
        """
        return SIAResults(self.execute_votable(), url=self.queryurl, session=self._session)


class SIAResults(DatalinkResultsMixin, DALResults):
    """
    The list of matching images resulting from an image (SIA) query.
    Each record contains a set of metadata that describes an available
    image matching the query constraints.  The number of records in
    the results is available via the :py:attr:`nrecs` attribute or by
    passing it to the Python built-in ``len()`` function.

    This class supports iterable semantics; thus,
    individual records (in the form of
    :py:class:`~pyvo.dal.sia2.ObsCoreRecord` instances) are typically
    accessed by iterating over an ``SIAResults`` instance.

    >>> results = pyvo.imagesearch(url, pos=[12.24, -13.1], size=0.1)
    >>> for image in results:
    ...     print("{0}: {1}".format(image.title, title.getdataurl()))

    Alternatively, records can be accessed randomly via
    :py:meth:`getrecord` or through a Python Database API (v2)
    Cursor (via :py:meth:`~pyvo.dal.query.DALResults.cursor`).
    Column-based data access is possible via the
    :py:meth:`~pyvo.dal.query.DALResults.getcolumn` method.

    ``SIAResults`` is essentially a wrapper around an Astropy
    :py:mod:`~astropy.io.votable`
    :py:class:`~astropy.io.votable.tree.Table` instance where the
    columns contain the various metadata describing the images.
    One can access that VOTable directly via the
    :py:attr:`~pyvo.dal.query.DALResults.votable` attribute.  Thus,
    when one retrieves a whole column via
    :py:meth:`~pyvo.dal.query.DALResults.getcolumn`, the result is
    a Numpy array.  Alternatively, one can manipulate the results
    as an Astropy :py:class:`~astropy.table.table.Table` via the
    following conversion:

    >>> table = results.votable.to_table()

    ``SIAResults`` supports the array item operator ``[...]`` in a
    read-only context.  When the argument is numerical, the result
    is an
    :py:class:`~pyvo.dal.sia2.ObsCoreRecord` instance, representing the
    record at the position given by the numerical index.  If the
    argument is a string, it is interpreted as the name of a column,
    and the data from the column matching that name is returned as
    a Numpy array.
    """

    def getrecord(self, index):
        """
        return a representation of a sia result record that follows
        dictionary semantics. The keys of the dictionary are those returned by
        this instance's fieldnames attribute. The returned record has
        additional image-specific properties

        Parameters
        ----------
        index : int
           the integer index of the desired record where 0 returns the first
           record

        Returns
        -------
        ObsCoreMetadataRecord
           a dictionary-like wrapper containing the result record metadata.

        Raises
        ------
        IndexError
           if index is negative or equal or larger than the number of rows in
           the result table.

        See Also
        --------
        Record
        """
        return ObsCoreRecord(self, index, session=self._session)


class ObsCoreRecord(SodaRecordMixin, DatalinkRecordMixin, Record,
                    ObsCoreMetadata):
    """
    a dictionary-like container for data in a record from the results of an
    image (SIAv2) search, describing an available image in ObsCore format.

    The commonly accessed metadata which are stadardized by the SIA
    protocol are available as attributes.  If the metadatum accessible
    via an attribute is not available, the value of that attribute
    will be None.  All metadata, including non-standard metadata, are also
    acessible via the ``get(`` *key* ``)`` function (or the [*key*]
    operator) where *key* is table column name.
    """

    #          OBSERVATION INFO
    @property
    def data_type(self):
        """
        Data product (file content) primary type. This is coded as a string
        that conveys a general idea of the content and organization of a
        dataset.
        """
        return self['dataproduct_type'].decode('utf-8')

    @property
    def data_subtype(self):
        """
        Data product more specific type
        """
        if 'dataproduct_subtype' in self.keys():
            return self['dataproduct_subtype'].decode('utf-8')
        return None

    @property
    def calib_level(self):
        """
        Calibration level of the observation: in {0, 1, 2, 3, 4}
        """
        return int(self['calib_level'])

    #          TARGET INFO
    @property
    def target_name(self):
        """
        The target_name attribute contains the name of the target of the
        observation, if any. This is typically the name of an astronomical
        object, but could be the name of a survey field.
        The target name is most useful for output, to identify the target of
        an observation to the user. In queries it is generally better to refer
        to astronomical objects by position, using a name resolver to convert
        the target name into a coordinate (when possible).
        """
        return self['target_name'].decode('utf-8')

    @property
    def target_class(self):
        """
        This field indicates the type of object that was pointed for this
        observation. It is a string with possible values defined in a special
        vocabulary set to be defined: list of object classes (or types) used
        by the SIMBAD database, NED or defined in another IVOA vocabulary.
        """
        if 'target_class' in self.keys():
            return self['target_class'].decode('utf-8')
        return None

    #          DATA DESCRIPTION
    @property
    def id(self):
        """
        Collection specific nternal ID given by the ObsTAP service
        """
        return self['obs_id'].decode('utf-8')

    @property
    def title(self):
        """
        Brief description of dataset in free format
        """
        if 'obs_title' in self.keys():
            return self['obs_title'].decode('utf-8')
        return None

    @property
    def collection(self):
        """
        The name of the collection (DataID.Collection) identifies the data
        collection to which the data product belongs. A data collection can be
        any collection of datasets which are alike in some fashion. Typical
        data collections might be all the data from a particular telescope,
        instrument, or survey. The value is either the registered shortname
        for the data collection, the full registered IVOA identifier for the
        collection, or a data provider defined short name for the collection.
        Examples: HST/WFPC2, VLT/FORS2, CHANDRA/ACIS-S, etc.
        """
        return self['obs_collection'].decode('utf-8')

    @property
    def create_date(self):
        """
        Date when the dataset was created
        """
        if 'obs_create_date' in self.keys():
            return time.Time(self['obs_create_date'])
        return None

    @property
    def creator_name(self):
        """
        The name of the institution or entity which created the dataset.
        """
        if 'obs_creator_name' in self.keys():
            return self['obs_creator_name'].decode('utf-8')
        return None

    @property
    def creator_did(self):
        """
        IVOA dataset identifier given by its creator.
        """
        if 'obs_creator_did' in self.keys():
            return self['obs_creator_did'].decode('utf-8')
        return None

    #         CURATION INFORMATION
    @property
    def release_date(self):
        """
        Observation release date
        """
        if 'obs_release_date' in self.keys():
            return time.Time(self['obs_release_date'])
        return None

    @property
    def global_id(self):
        """
        ID for the Dataset given by the publisher.
        """
        return self['obs_publisher_did'].decode('utf-8')

    @property
    def publisher_id(self):
        """
        IVOA-ID for the Publisher. It will also be globally unique since each
        publisher has a unique registered publisher ID
        """
        if 'publisher_id' in self.keys():
            return self['publisher_id'].decode('utf-8')
        return None

    @property
    def bib_reference(self):
        """
        URL or bibcode for documentation. This is a forward link to major
        publications which reference the dataset.
        """
        if 'bib_reference' in self.keys():
            return self['bib_reference'].decode('utf-8')
        return None

    @property
    def data_rights(self):
        """
        This parameter allows mentioning the availability of a dataset.
        Possible values are: public, secure, or proprietary.
        """
        if 'data_rights' in self.keys():

            return self['data_rights'].decode('utf-8')

    #           ACCESS INFORMATION
    @property
    def access_url(self):
        """
        The access_url column contains a URL that can be used to download the
        data product (as a file of some sort). Access URLs are not guaranteed
        to remain valid and unchanged indefinitely. To access a specific data
        product after a period of time (e.g., days or weeks) a query should be
        performed to obtain a fresh access URL.
        """
        return self['access_url'].decode('utf-8')

    @property
    def res_format(self):
        """
        Content format of the dataset. The value of access_format should be a
        MIME type, either a standard MIME type, an extended MIME type from
        the above table, or a new custom MIME type defined by the data
        provider.
        """
        return self['access_format'].decode('utf-8')

    @property
    def access_estsize(self):
        """
        The approximate size (in kilobytes) of the file available via the
        access_url. This is used only to gain some idea of the size of a data
        product before downloading it, hence only an approximate value is
        required. Provision of dataset size estimates is important whenever it
        is possible that datasets can be very large.
        """
        return self['access_estsize']*1000*u.byte

    #           SPATIAL CHARACTERISATION
    @property
    def pos(self):
        """
        Central Spatial Position in ICRS
        """
        return SkyCoord(self['s_ra']*u.deg, self['s_dec']*u.deg, frame='icrs')

    @property
    def radius(self):
        """
        Approximate size of the covered region as the radius of a containing
        circle. For most data products the value given should be large enough
        to include the entire area of the observation; coverage within the
        bounded region need not be complete, for example if the specified
        radius encompasses a rotated rectangular region. For observations
        which do not have a well-defined boundary, e.g. radio or
        high energy observations, a characteristic value should be given.
        The radius attribute provides a simple way to characterize and use
        (e.g. for discovery computations) the approximate spatial coverage of a
        data product. The spatial coverage of a data product can be more
        precisely specified using the region attribute.
        """
        return self['s_fov']/2*u.deg

    @property
    def region(self):
        """
        Sky region covered by the data product (expressed in ICRS frame).
        It can be used to precisely specify the covered spatial region of a
        data product.
        It is often an exact, or almost exact, representation of the
        illumination region of a given observation defined in a standard way
        by the concept of Support in the Characterisation data model.
        """
        return self['s_region']

    @property
    def spatial_resolution(self):
        """
        Spatial resolution of data specifies a reference value chosen by the
        data provider for the estimated spatial resolution of the data product
        in arcseconds. This refers to the smallest spatial feature in the
        observed signal that can be resolved.
        In cases where the spatial resolution varies across the field the best
        spatial resolution (smallest resolvable spatial feature) should be
        specified. In cases where the spatial frequency sampling of an
        observation is complex (e.g., interferometry) a typical value for
        spatial resolution estimate should be given; additional
        characterisation may be necessary to fully specify the spatial
        characteristics of the data.
        """
        return self['s_resolution']*u.arcsec

    @property
    def spatial_xel(self):
        """
        Tuple representing the number of elements along the coordinates of
        spatial axis
        """
        return (self['s_xel1'], self['s_xel2'])

    @property
    def spatial_ucd(self):
        """
        UCD for the nature of the spatial axis (pos or u,v data)
        """
        return self.get('s_ucd', None)

    @property
    def spatial_unit(self):
        """
        Unit used for spatial axis
        """
        return self.get('s_unit', None)

    @property
    def resolution_min(self):
        """
        Resolution min value on spatial axis (FHWM of PSF)
        """
        return self.get('s_resolution_min', None)

    @property
    def resolution_max(self):
        """
        Resolution max value on spatial axis (FHWM of PSF)
        """
        return self.get('s_resolution_max', None)

    @property
    def spatial_calib_status(self):
        """
        A string to encode the calibration status along the spatial axis
        (astrometry). Possible values could be {uncalibrated, raw, calibrated}
        """
        return self.get('s_calib_status', None)

    @property
    def spatial_stat_error(self):
        """
        This parameter gives an estimate of the astrometric statistical error
        after the astrometric calibration phase.
        """
        return self.get('s_stat_error', None)

    @property
    def pixel_scale(self):
        """
        This corresponds to the sampling precision of the data along the
        spatial axis. It is stored as a real number corresponding to the
        spatial sampling period, i.e., the distance in world coordinates
        system units between two pixel centers. It may contain two values if
        the pixels are rectangular.
        """
        return self.get('s_pixel_scale', None)

    #           TIME CHARACTERISATION
    @property
    def time_xel(self):
        """
        Number of elements along the time axis
        """
        return self['t_xel']

    @property
    def ref_pos(self):
        """
        Time Axis Reference Position as defined in STC REC, Section 4.4.1.1.1
        """
        return self.get('t_ref_pos', None)

    @property
    def time_bounds(self):
        """
        Tuple containing the start and end time of the observation specified
         in MJD. In case of data products result of the combination of multiple
         frames, min bound must be the minimum of the start times, and max
         bound as the maximum of the stop times.
        """
        return (time.Time(self['t_min']),
                time.Time(self['t_max']))

    @property
    def exptime(self):
        """
        Total exposure time. For simple exposures, this is just the time_bounds
         size expressed in seconds. For data where the detector is not active
         at all times (e.g. data products made by combining exposures taken at
         different times), the t_exptime will be smaller than the time_bounds
         interval. For data where the xptime is not constant over the entire
         data product, the median exposure time per pixel is a good way to
         characterize the typical value. In some cases, exptime is generally
         used as an indicator of the relative sensitivity (depth) within a
         single data collection (e.g. obs_collection); data providers should
         supply a suitable relative value when it is not feasible to define or
         compute the true exposure time.

        In case of targeted observations, on the contrary the exposure time is
        often adjusted to achieve similar signal to noise ratio for different
        targets.
        """
        return self['t_exptime']*u.second

    @property
    def time_resolution(self):
        """
        Estimated or average value of the temporal resolution.
        """
        return self['t_resolution']*u.second

    @property
    def time_calib_status(self):
        """
        Type of time coordinate calibration. Possible values are principally
        {uncalibrated, calibrated, raw, relative}. This may be extended for
        specific time domain collections.
        """
        return self.get('t_calib_status', None)

    @property
    def time_stat_error(self):
        """
        Time coord statistical error on the time measurements in seconds
        """
        if 't_stat_error' in self.keys():
            return self['t_stat_error']*u.second
        return None

    #           SPECTRAL CHARACTERISATION
    @property
    def spectral_xel(self):
        """
        Number of elements along the spectral axis
        """
        return self['em_xel']

    @property
    def spectral_ucd(self):
        """
        Nature of the spectral axis
        """
        return self.get('em_ucd', None)

    @property
    def spectral_unit(self):
        """
        Units along the spectral axis
        """
        return self.get('em_unit', None)

    @property
    def spectral_calib_status(self):
        """
        This attribute of the spectral axis indicates the status of the data
        in terms of spectral calibration. Possible values are defined in the
        Characterisation Data Model and belong to {uncalibrated , calibrated,
        relative, absolute}.
        """
        return self.get('em_calib_status', None)

    @property
    def spectral_bounds(self):
        """
        Tuple containing the limits of the spectral interval covered by the
        observation, in short em_min and em_max.
        """
        return (self['em_min']*u.meter, self['em_max']*u.meter)

    @property
    def resolving_power(self):
        """
        Average estimation for the spectral resolution power stored as a
        double value, with no unit.
        """
        return self["em_res_power"]

    @property
    def resolving_power_min(self):
        """
        Resolving power min value on spectral axis
        """
        return self.get('em_res_power_min', None)

    @property
    def resolving_power_max(self):
        """
        Resolving power max value on spectral axis
        """
        return self.get('em_res_power_max', None)

    @property
    def spectral_resolution(self):
        """
        A mean estimate of the resolution, e.g. Full Width at Half Maximum
        (FWHM) of the Line Spread Function (or LSF). This can be used for
        narrow range spectra whereas in the majority of cases, the resolution
        power is preferable due to the LSF variation along the spectral axis.
        """
        if 'em_resolution' in self.keys():
            return self['em_resolution']*u.meter
        return None

    @property
    def spectral_stat_error(self):
        """
        Spectral coord statistical error (accuracy along the spectral axis)
        """
        if 'em_stat_error' in self.keys():
            return self['em_stat_error']*u.meter
        return None

    #           OBSERVABLE AXIS
    @property
    def obs_ucd(self):
        """
        Nature of the observable axis within the data product
        """
        return self.get('o_ucd', None)

    @property
    def obs_unit(self):
        """
        Units along the observable axis
        """
        return self.get('o_unit', None)

    @property
    def obs_calib_status(self):
        """
        Type of calibration applied on the Flux observed (or other observable
        quantity).
        """
        return self.get('o_calib_status', None)

    @property
    def obs_stat_error(self):
        """
        Statistical error on the Observable axis.
        Note: the return value has the units defined in unit
        """
        return self.get('o_stat_error', None)

    #           POLARIZATION CHARACTERISATION
    @property
    def pol_xel(self):
        """
        Number of different polarization states present in the data. The
        default value is 0, indicating that polarization was not explicitly
        observed. Corresponding values are stored in the `pol` property
        """
        return self['pol_xel']

    @property
    def pol(self):
        """
        List of polarization states present in the data file. Possible values
        are: {I Q U V RR LL RL LR XX YY XY YX POLI POLA}. Values in the
        set are separated by the '/' character. A leading / character must
        start the list and a trailing / character must end it. It should be
        ordered following the above list, compatible with the FITS list table
        for polarization definition.
        """
        return self.get('pol_states').decode('utf-8')

    #           PROVENANCE
    @property
    def instrument(self):
        """
        The name of the instrument used for the acquisition of the data
        """
        return self['instrument_name'].decode('utf-8')

    @property
    def facility(self):
        """
        Name of the facility or observatory used to collect the data
        """
        if 'facility_name' in self.keys():
            return self['facility_name'].decode('utf-8')
        return None

    @property
    def proposal_id(self):
        """
        Identifier of proposal to which observation belongs
        """
        return self.get('proposal_id', None)
