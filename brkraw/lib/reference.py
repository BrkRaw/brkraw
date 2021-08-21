# REGEX patterns
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
# [20210820] Add-paravision 360 related. @[number of repititions]([number]) ex) @5(0)
ptrn_at_array       = r'@(\d*)\*\(([-]?\d*[.]?\d*[eE]?[-]?\d*?)\)'

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

SLICE_ORIENT = {0: {1: 'L->R', 3: 'R->L'},
                1: {1: 'P->A', 3: 'A->P'},
                2: {1: 'F->H', 3: 'F->H'},
                }

ISSUE_REPORT = 'Please report the issue at (https://github.com/dvm-shlee/bruker/issues) with the error message.'

ERROR_MESSAGES = {'ImportError'         : '[{}] is not recognized as ParavisionDataset.',
                  'NoSlicePacksDef'     : 'NoneType VisuCoreSlicePacksDef.',
                  'SliceDistDatatype'   : 'unexpected datatype of VisuCoreSliceDist.',
                  'SlicePacksSlices'    : 'unexpected datatype of VisuCoreSlicePacksSlices',
                  'DimType'             : 'non compatible dimension type.',
                  'NumOrientMatrix'     : 'unexpected number of element in VisuCoreOrientation.',
                  'NumSlicePosition'    : 'unexpected number of element in VisuCorePosition.',
                  'PhaseEncDir'         : 'unexpected phase encoding direction.',
                  'NotIntegrated'       : 'not integrated method, please contact developer.'
                  }

# BIDS v1.2.2
# Below is the list of METADATA keywords that BIDS recommended
COMMON_METADATA_FIELD = \
    dict(Recommended    = [  # SCANNER_HARDWARE
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

             Optional   = [  # RF_AND_CONTRAST
                           'NegativeContrast',

                             # ACQUISITION_SPECIFIC
                           'ContrastBolusIngredient'],

             Deprecated = [  # SCANNER_HARDWARE
                           'HardcopyDeviceSoftwareVersion'])

# Matadata Field Mapping for Bruker PvDataset
# BIDS Meta data will be automatically created according to below reference.
# If list is entered as value, each parameter will be tested and the first available value will be returned.
# If dict is entered as value, below condition will be tested.
#   If key - where pair:  parse value from given key and return index of 'where' from these values
#   If key - idx pair:    parse value from given key and return value of given 'idx'
#   If 'Equation' in key: each key assigned as local variable and test in Equation will be executed to return the value
#   Else, new key - value dictionary will be return (for the cases with sub-keys)
# If string is entered as value, The value of given parameter will be parsed from parameter files
COMMON_META_REF = \
    dict(Manufacturer                   = 'VisuManufacturer',
         ManufacturersModelName         = 'VisuStation',
         DeviceSerialNumber             = 'VisuSystemOrderNumber',
         StationName                    = 'VisuStation',
         SoftwareVersion                = 'VisuAcqSoftwareVersion',
         MagneticFieldStrength          = dict(Freq     = 'VisuAcqImagingFrequency',
                                               Equation = 'Freq / 42.576'),
         ReceiveCoilName                = 'VisuCoilReceiveName',
         ReceiveCoilActiveElements      = 'VisuCoilReceiveType',
         GradientSetType                = 'ACQ_status',
         MRTransmitCoilSequence         = dict(Name         = 'VisuCoilTransmitName',
                                               Manufacture  = 'VisuCoilTransmitManufacturer',
                                               Type         = 'VisuCoilTransmitType'),
         CoilConfigName                 = 'ACQ_coil_config_file',  # if Transmit and Receive coil info in None
         MatrixCoilMode                 = 'ACQ_experiment_mode',
         CoilCombinationMethod          = None,

         # SEQUENCE_SPECIFIC
         PulseSequenceType              = 'PULPROG',  # 'VisuAcqEchoSequenceType'
         ScanningSequence               = 'VisuAcqSequenceName',
         SequenceVariant                = 'VisuAcqEchoSequenceType',
         ScanOptions                    = dict(RG   = 'VisuRespSynchUsed',
                                               CG   = 'VisuCardiacSynchUsed',
                                               PFF  = dict(key = 'VisuAcqPartialFourier',
                                                           idx = 0),
                                               PFP  = dict(key = 'VisuAcqPartialFourier',
                                                           idx = 1),
                                               FC   = 'VisuAcqFlowCompensation',
                                               SP   = 'PVM_FovSatOnOff',
                                               FP   = 'VisuAcqSpectralSuppression'),
         SequenceName                   = ['VisuAcquisitionProtocol',
                                           'ACQ_protocol_name'],  # if first component are None
         PulseSequenceDetails           = 'ACQ_scan_name',
         NonlinearGradientCorrection    = 'VisuAcqKSpaceTraversal',

         # IN_PLANE_SPATIAL_ENCODING
         NumberShots                    = 'VisuAcqKSpaceTrajectoryCnt',
         ParallelReductionFactorInPlane = 'ACQ_phase_factor',
         ParallelAcquisitionTechnique   = None,
         PartialFourier                 = 'VisuAcqPartialFourier',
         PartialFourierDirection        = None,
         PhaseEncodingDirection         = [dict(key         = 'VisuAcqGradEncoding',
                                                where       = 'phase_enc'),
                                           'VisuAcqImagePhaseEncDir'],  # Deprecated
         EffectiveEchoSpacing           = dict(BWhzPixel    = 'VisuAcqPixelBandwidth',
                                               MatSizePE    = dict(key='PVM_EncMatrix',
                                                                   idx=[dict(key    = 'VisuAcqGradEncoding',
                                                                             where  = 'phase_enc'),
                                                                        1]),  # PV5.1
                                               ACCfactor    = 'ACQ_phase_factor',
                                               Equation     = '(1 / (MatSizePE * BWhzPixel)) / ACCfactor'),  # in second
         TotalReadoutTime               = dict(ETL          = 'VisuAcqEchoTrainLength',
                                               BWhzPixel    = 'VisuAcqPixelBandwidth',
                                               ACCfactor    = 'ACQ_phase_factor',
                                               Equation     = '(1 / BWhzPixel) / ACCfactor'),

         # TIMING_PARAMETERS
         EchoTime                       = dict(TE           = 'VisuAcqEchoTime',
                                               Equation     = 'np.array(TE)/1000'),
         InversionTime                  = 'VisuAcqInversionTime',
         SliceTiming                    = dict(TR           = 'VisuAcqRepetitionTime',
                                               Num_of_Slice = 'VisuCoreFrameCount',
                                               Order        = 'ACQ_obj_order',
                                               Equation     = 'np.linspace(0, TR/1000, Num_of_Slice + 1)[Order]'),
         SliceEncodingDirection         = [dict(key         = 'VisuAcqGradEncoding',
                                                where       = 'slice_enc'),
                                           dict(EncSeq      = 'VisuAcqGradEncoding',
                                                Equation    = 'len(EncSeq)')],
         DwellTime                      = dict(BWhzPixel    ='VisuAcqPixelBandwidth',
                                               Equation     ='1/BWhzPixel'),

         # RF_AND_CONTRAST, SLICE_ACCELERATION
         FlipAngle                      = 'VisuAcqFlipAngle',
         MultibandAccerlationFactor     = None,
         AnatomicalLandmarkCoordinates  = None,

         # INSTITUTION_INFORMATION
         InstitutionName                = 'VisuInstitution',
         InstitutionAddress             = None,
         InstitutionalDepartmentName    = None)


FMRI_META_REF = \
    dict(RepetitionTime                 = dict(TR           = 'VisuAcqRepetitionTime',
                                               Equation     = 'TR/1000'),
         VolumeTiming                   = dict(TR           = 'VisuAcqRepetitionTime',
                                               NR           = 'PVM_NRepetitions',
                                               Equation     = '(np.arange(NR)*(TR/1000)).tolist()'),
         TaskName                       = None,

         # RECOMMENDED
         # - timing parameters
         NumberOfVolumesDiscardedByScanner  = 'PVM_DummyScans',
         NumberOfVolumesDiscardedByUser     = None,
         DelayTime                      = None,
         AcquisitionDuration            = None,
         DelayAfterTrigger              = None,

         # - fMRI task information
         Instructions                   = None,
         TaskDescription                = None,
         CogAtlasID                     = None,
         CogPOID                        = None
         )


FIELDMAP_META_REF = \
    dict(IntendedFor                    = '',
         )

DATASET_DESC_REF = \
    dict(Name='',
         BIDSVersion='1.2.2',
         License='',
         Authors=[''],
         Acknowledgements='',
         HowToAsknowledge='',
         Funding=[''],
         EthicApprovals='',
         ReferenceAndLinks='',
         DatasetDOI='')

XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))
