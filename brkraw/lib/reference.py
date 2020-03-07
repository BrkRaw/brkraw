# REGEX patterns
# ptrn_param         = r'^\#\#(?P<key>.*)\=(?P<value>.*){}$'.format(re.escape('\n'))
ptrn_param          = r'^\#\#(?P<key>.*)\=(?P<value>.*)$'
ptrn_key            = r'^\$(?P<key>.*)'
ptrn_array          = r"\((?P<array>[^()]*)\)"
ptrn_complex_array  = r"\((?P<comparray>\(.*)\)$"
ptrn_comment        = r'\$\$.*'
ptrn_float          = r'^-?\d+\.\d+$'
ptrn_engnotation    = r'^-?[0-9.]+e-?[0-9.]+$'
ptrn_integer        = r'^[-]*\d+$'
ptrn_string         = r'^\<(?P<string>[^>]*)\>$'
ptrn_arraystring    = r'\<(?P<string>[^>]*)\>[,]*'
ptrn_bisstring      = r'\<(?P<string>\$Bis[^>]*)\#\>'
ptrn_braces         = r'\((?P<contents>[^()]*)\)'

# Conditional variables
HEADER = 0
PARAMETER = 1

# Parameters
WORDTYPE = \
    dict(_32BIT_SGN_INT     = 'i',
         _16BIT_SGN_INT     = 'h',
         _8BIT_UNSGN_INT    = 'B',
         _32BIT_FLOAT       = 'f')
BYTEORDER = \
    dict(littleEndian       = '<',
         bigEndian          = '>')

SLICE_ORIENT = {0:{1:'L->R', 3:'R->L'},
                1:{1:'P->A', 3:'A->P'},
                2:{1:'F->H', 3:'F->H'},
                }

ERROR_MESSAGES = {'ImportError'         : '[{}] is not recognized as ParavisionDataset.',
                  'NoSlicePacksDef'     : 'NoneType VisuCoreSlicePacksDef.',
                  'SliceDistDatatype'   : 'unexpected datatype of VisuCoreSliceDist.',
                  'SlicePacksSlices'    : 'unexpected datatype of VisuCoreSlicePacksSlices',
                  'DimType'             : 'non compatible dimention type.',
                  'NumOrientMatrix'     : 'unexpected number of element in VisuCoreOrientation.',
                  'NumSlicePosition'    : 'unexpected number of element in VisuCorePosition.',
                  'PhaseEncDir'         : 'unexpected phase encoding direction.',
                  'NotIntegrated'       : 'not integrated method, please contact developer.'
                  }

# BIDS v1.2.2
COMMON_METADATA_FIELD = \
dict(Recommended    = [# SCANNER_HARDWARE
                       'Manufacturer',
                       'ManufacturersModelName',
                       'DeviceSerialNumber',
                       'StationName',
                       'SoftwareVersion',
                       'MagneticFieldStrength',
                       'ReceiveCoilName',
                       'ReceiveCoilActiveElements',
                       'GradientSetType',
                       'MRTransmitCoilSequence',
                       'MatrixCoilMode',
                       'CoilCombinationMethod',

                        # SEQUENCE_SPECIFIC
                       'PulseSequenceType',
                       'ScanningSequence',
                       'SequenceVariant',
                       'ScanOptions',
                       'SequenceName',
                       'PulseSequenceDetails',
                       'NonlinearGradientCorrection',

                        # IN_PLANE_SPATIAL_ENCODING
                       'NumberShots',
                       'ParallelReductionFactorInPlane',
                       'ParallelAcquisitionTechnique',
                       'PartialFourier',
                       'PartialFourierDirection',
                       'PhaseEncodingDirection',
                       'EffectiveEchoSpacing',
                       'TotalReadoutTime',

                        # TIMING_PARAMETERS
                       'EchoTime',
                       'InversionTime',
                       'SliceTiming',
                       'SliceEncodingDirection',
                       'DwellTime',

                        # RF_AND_CONTRAST, SLICE_ACCELERATION
                       'FlipAngle',
                       'MultibandAccerlationFactor',
                       'AnatomicalLandmarkCoordinates',

                        # INSTITUTION_INFORMATION
                       'InstitutionName',
                       'InstitutionAddress',
                       'InstitutionalDepartmentName'],

         Optional   = [ # RF_AND_CONTRAST
                       'NegativeContrast',

                        # ACQUISITION_SPECIFIC
                       'ContrastBolusIngredient'],

         Deprecated = [ # SCANNER_HARDWARE
                       'HardcopyDeviceSoftwareVersion'])

# Matadata Field Mapping for Bruker PvDataset
METADATA_FILED_INFO = \
    dict(Manufacturer = 'VisuManufacturer',
         ManufacturersModelName = 'VisuStation',
         DeviceSerialNumber = 'VisuSystemOrderNumber',
         StationName = 'VisuStation',
         SoftwareVersion = 'VisuAcqSoftwareVersion',
         MagneticFieldStrength = ['VisuAcqImagingFrequency', 'divide', 42.576],
         ReceiveCoilName = 'VisuCoilReceiveName',
         ReceiveCoilActiveElements = 'VisuCoilReceiveType',
         GradientSetType = 'ACQ_status',
         MRTransmitCoilSequence = ['VisuCoilTransmitName',
                                   'VisuCoilTransmitManufacturer',
                                   'VisuCoilTransmitType'],
         CoilConfigName = 'ACQ_coil_config_file', # if Transmit and Receive coil info in None
         MatrixCoilMode = 'ACQ_experiment_mode',
         CoilCombinationMethod = None,

         # SEQUENCE_SPECIFIC
         PulseSequenceType = 'VisuAcqEchoSequenceType',
         ScanningSequence = 'VisuAcqSequenceName',
         SequenceVariant = 'VisuAcqEchoSequenceType',
         ScanOptions = dict(RG = 'VisuRespSynchUsed',
                            CG = 'VisuCardiacSynchUsed',
                            PFF = ['VisuAcqPartialFourier', 0],
                            PFP = ['VisuAcqPartialFourier', 1],
                            FC = 'VisuAcqFlowCompensation',
                            SP = 'PVM_FovSatOnOff',
                            FP = 'VisuAcqSpectralSuppression'),
         SequenceName = ['VisuAcquisitionProtocol',
                         'ACQ_protocol_name'], # if first component are None
         PulseSequenceDetails = 'ACQ_scan_name',
         NonlinearGradientCorrection = 'VisuAcqKSpaceTraversal',

         # IN_PLANE_SPATIAL_ENCODING
         NumberShots = 'VisuAcqKSpaceTrajectoryCnt',
         ParallelReductionFactorInPlane = 'ACQ_phase_factor',
         ParallelAcquisitionTechnique = None,
         PartialFourier = 'VisuAcqPartialFourier',
         PartialFourierDirection = None,
         PhaseEncodingDirection = [['VisuAcqGradEncoding', 'phase_enc'],
                                   'VisuAcqImagePhaseEncDir'], # Deprecated
         EffectiveEchoSpacing = dict(ETL= 'VisuAcqEchoTrainLength',
                                     BWhzPixel= 'VisuAcqPixelBandwidth',
                                     ACCfactor= 'ACQ_phase_factor',
                                     Equation= '(1000 * 1 / (ETL * BWhzPixel)) / ACCfactor'), # in millisecond
         TotalReadoutTime = '',

         # TIMING_PARAMETERS
         EchoTime = 'VisuAcqEchoTime',
         InversionTime = 'VisuAcqInversionTime',
         SliceTiming = dict(TR = 'VisuAcqRepetitionTime',
                            Num_of_Slice='VisuCoreFrameCount',
                            Order='ACQ_obj_order',
                            Equation='np.linspace(0, TR, Num_of_Slice + 1)["ACQ_obj_order"]'),
         SliceEncodingDirection = dict(_3D=['VisuAcqGradEncoding', 'slice_enc'],
                                       _2D=['len(VisuAcqGradEncoding)']),
         DwellTime = dict(BWhzPixel='VisuAcqPixelBandwidth',
                          Equation='1/BWhzPixel'),

         # RF_AND_CONTRAST, SLICE_ACCELERATION
         FlipAngle = 'VisuAcqFlipAngle',
         MultibandAccerlationFactor = None,
         AnatomicalLandmarkCoordinates = None,

         # INSTITUTION_INFORMATION
         InstitutionName = 'VisuInstitution',
         InstitutionAddress = None,
         InstitutionalDepartmentName = None)


XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))
