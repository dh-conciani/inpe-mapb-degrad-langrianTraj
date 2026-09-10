# MapBiomas Brazil Collection 10.1
# End-to-end Earth Engine / Colab pipeline
#
# PHASE A:
#   Build/materialize all 41 target years (1979-2019) at 1 km.
#
# PHASE B:
#   Load those materialized assets, run QA sequentially,
#   and export the final 41 annual GeoTIFFs.
#
# FINAL PRIMARY BAND ORDER:
#   TTF, TTFd, TTS, TTCe, TTP, TTA, TTW, OTH, completeness
#
# IMPORTANT MISSING-DATA / LEGEND INTERPRETATION:
#   MapBiomas class 27 ("Nao Observado") is treated as missing, NOT OTH.
#   Any other unexpected observed MapBiomas code follows the original JS:
#       it remains valid and defaults to OTH,
#       while a QA flag records its presence.
#
# EARLY-YEAR TEMPORAL PROXIES:
#   target 1979-1984:
#       LULC_1985 + edge_1985 + fire_1985
#       + secondary_1987 + logging_1988
#
#   Secondary vegetation begins in 1987:
#       target 1985-1986 -> secondary_1987
#
#   Logging begins in 1988:
#       target 1985-1987 -> logging_1988
#
#   Thus 1979-1985 use the same source-year combination and should be
#   identical under this explicit proxy construction.
#
# ==============================================================================


# ==============================================================================
# 0. COLAB SETUP
# ==============================================================================

# Run this once if needed:
# !pip -q install -U earthengine-api pandas

import ee
import json
import pandas as pd
from datetime import datetime, timezone


# ------------------------------------------------------------------------------
# USER CONFIGURATION
# ------------------------------------------------------------------------------

EE_PROJECT = 'mapbiomas-brazil'

# Earth Engine folder for materialized 1-km intermediate assets.
INTERMEDIATE_ASSET_ROOT = (
    'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/'
    '1KM-FRAC'
)

# Final GeoTIFF destination:
#   'DRIVE' or 'GCS'
EXPORT_DESTINATION = 'GCS'

# Google Drive.
DRIVE_FOLDER = 'MapBiomas_fractional_1km_1979_2019'

# Google Cloud Storage, used only when EXPORT_DESTINATION == 'GCS'.
GCS_BUCKET = 'shared-development-storage'
GCS_PREFIX = 'AUXILIARES/DEGRADACAO/COL_101/1km-frac'


# ------------------------------------------------------------------------------
# PHASE FLAGS
# ------------------------------------------------------------------------------

# Recommended use:
#
# FIRST RUN:
#   RUN_PHASE_A_CREATE_ASSETS = True
#   all Phase-B flags = False
#
# Wait until all 41 EE asset tasks finish.
#
# SECOND RUN:
#   RUN_PHASE_A_CREATE_ASSETS = False
#   RUN_PHASE_B_QA = True
#   RUN_PHASE_B_EXPORT_GEOTIFF = True
#   RUN_PHASE_B_EXPORT_LOW_COMPLETENESS_STACK = True

# Safe defaults: choose ONE phase at a time.
RUN_PHASE_A_CREATE_ASSETS = True

RUN_PHASE_B_QA = True
RUN_PHASE_B_EXPORT_GEOTIFF = True

RUN_PHASE_B_EXPORT_LOW_COMPLETENESS_STACK = True


# Require every 1979-2019 intermediate asset before Phase B.
STRICT_ASSET_CHECK = True


# ------------------------------------------------------------------------------
# WORKFLOW SETTINGS
# ------------------------------------------------------------------------------

START_YEAR = 1985
END_YEAR = 2024

FINAL_START_YEAR = 1979
FINAL_END_YEAR = 2024

SECONDARY_START_YEAR = 1987

# The secondary-vegetation product starts in 1987.
# For target years 1979-1986, use the 1987 secondary map as a proxy.
SECONDARY_FALLBACK_YEAR = 1987

LOGGING_START_YEAR = 1988

# The logging product begins in 1988.
# For target years 1979-1987, use logging_1988 as a temporal proxy.
LOGGING_FALLBACK_YEAR = 1988

EDGE_THRESHOLD_M = 150

COMPLETENESS_THRESHOLD = 0.90

SUM_TOLERANCE = 1e-6


# Early-year source-year policy:
#
# target 1979-1984:
#   LULC=1985 proxy
#   edge=1985 proxy
#   fire=1985 proxy
#   secondary=1987 proxy
#   logging=1988 proxy
#
# target 1985:
#   LULC=1985, edge=1985, fire=1985,
#   secondary=1987 proxy, logging=1988 proxy
#
# target 1986:
#   LULC=1986, edge=1986, fire=1986,
#   secondary=1987 proxy, logging=1988 proxy
#
# target 1987:
#   LULC=1987, edge=1987, fire=1987,
#   secondary=1987, logging=1988 proxy
#
# target >=1988:
#   all annual inputs use their matching target year.
#
# Therefore 1979-1985 are built from the SAME source years:
#   LULC 1985 + edge 1985 + fire 1985 + secondary 1987 + logging 1988.
#
# This is a deliberate temporal-proxy strategy. It does NOT assert that
# fire/edge/logging observed in the proxy source year occurred in every
# earlier target year. The source-year provenance is written to metadata.


# ------------------------------------------------------------------------------
# EARTH ENGINE AUTHENTICATION
# ------------------------------------------------------------------------------

# In a fresh Colab runtime first run:
#
# ee.Authenticate()
#
# Then initialize:
ee.Initialize(project=EE_PROJECT)


# ==============================================================================
# 1. INPUT ASSETS
# ==============================================================================

ASSET_LULC = (
    'projects/mapbiomas-public/assets/brazil/lulc/collection10_1/'
    'mapbiomas_brazil_collection10_1_coverage_v1'
)

ASSET_SECONDARY = (
    'projects/mapbiomas-public/assets/brazil/lulc/collection10_1/'
    'mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3'
)

ASSET_EDGE = (
    'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/public/'
    'degradation_edge_area_col101_v2'
)

ASSET_FIRE = (
    'projects/mapbiomas-public/assets/brazil/fire/collection5/'
    'mapbiomas_fire_collection5_annual_burned_v1'
)

ASSET_LOGGING = (
    'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/public/'
    'logging_v2'
)


lulc = ee.Image(ASSET_LULC)
secondary = ee.Image(ASSET_SECONDARY)
edge = ee.Image(ASSET_EDGE)
fire = ee.Image(ASSET_FIRE)
logging = ee.Image(ASSET_LOGGING)


# ==============================================================================
# 1B. LIGHTWEIGHT INPUT-BAND VALIDATION
# ==============================================================================

def validate_input_bands():
    """Fail early if an expected annual band is missing."""

    checks = [
        (
            'LULC',
            lulc,
            [f'classification_{y}' for y in range(1985, 2020)],
        ),
        (
            'Secondary vegetation',
            secondary,
            [f'classification_{y}' for y in range(1987, 2020)],
        ),
        (
            'Edge',
            edge,
            [f'edge_{y}' for y in range(1985, 2020)],
        ),
        (
            'Fire',
            fire,
            [f'burned_area_{y}' for y in range(1985, 2020)],
        ),
        (
            'Logging',
            logging,
            [f'logging_{y}' for y in range(1988, 2020)],
        ),
    ]

    for label, image, expected in checks:
        available = set(image.bandNames().getInfo())
        missing = [band for band in expected if band not in available]

        if missing:
            raise RuntimeError(
                f'{label}: missing expected bands: {missing[:10]}'
            )

        print(
            f'{label}: OK ({len(expected)} required bands found)'
        )

    print(
        'Proxy policy: 1979-1984 use LULC/edge/fire 1985, '
        'secondary 1987 and logging 1988.'
    )

    print(
        'Proxy policy: 1985-1986 use secondary 1987; '
        '1985-1987 use logging 1988.'
    )


# Run once at startup. bandNames().getInfo() is small and avoids discovering
# a missing annual band only after large export tasks have been submitted.
validate_input_bands()


# ==============================================================================
# 2. OUTPUT CODES / BAND ORDER
# ==============================================================================

OUT = {
    'TTF': 1,
    'TTFd': 2,
    'TTS': 3,
    'TTCe': 4,
    'TTP': 5,
    'TTA': 6,
    'TTW': 7,
    'OTH': 8,
}


FRACTION_BANDS = [
    'TTF',
    'TTFd',
    'TTS',
    'TTCe',
    'TTP',
    'TTA',
    'TTW',
    'OTH',
]


FINAL_BANDS = FRACTION_BANDS + [
    'completeness',
]


# These are INTERNAL intermediate QA bands.
# They are not included in the final 9-band annual GeoTIFF.
QA_COUNT_BANDS = [
    'forest_base_count',
    'secondary_degradation_overlap_count',
    'unknown_class_count',
    'parent_class_count',
]


INTERMEDIATE_BANDS = FINAL_BANDS + QA_COUNT_BANDS


# ==============================================================================
# 3. MAPBIOMAS COLLECTION 10.1 CLASS MAPPING
# ==============================================================================

# Forest base.
CODES_FOREST = [
    3,
    5,
    6,
    49,
]


# Cerrado / Savanna.
CODES_TTCE = [
    4,
]


# Pasture.
CODES_TTP = [
    15,
]


# Agriculture.
CODES_TTA = [
    9,   # Silvicultura
    18,  # Agricultura
    19,  # Lavoura Temporaria
    20,  # Cana
    39,  # Soja
    40,  # Arroz
    41,  # Outras Lavouras Temporarias
    62,  # Algodao
    36,  # Lavoura Perene
    46,  # Cafe
    47,  # Citrus
    35,  # Dende
    48,  # Outras Lavouras Perenes
]


# Water.
CODES_TTW = [
    31,
    33,
]


# Explicit OTH.
#
# IMPORTANT:
# 27 is NOT here.
# Class 27 = Nao Observado is treated as missing data.
CODES_OTH = [
    11,  # Campo Alagado / Pantanosa
    12,  # Formacao Campestre
    32,  # Apicum
    29,  # Afloramento Rochoso
    50,  # Restinga Herbacea
    21,  # Mosaico de Usos
    23,  # Praia, Duna e Areal
    24,  # Area Urbanizada
    30,  # Mineracao
    75,  # Usina Fotovoltaica
    25,  # Outras Areas nao Vegetadas
]


# Hierarchical legend codes.
# Normally absent from terminal annual coverage.
# If present:
#   - mapped conservatively to OTH
#   - tracked in QA.
CODES_PARENT = [
    1,
    10,
    14,
    22,
    26,
]


# MapBiomas Not Observed.
CODE_NOT_OBSERVED = 27


# Secondary vegetation product:
# user-specified valid values.
CODES_SECONDARY = [
    3,
    5,
]


# ------------------------------------------------------------------------------
# STRICT RECLASSIFICATION TABLE
# ------------------------------------------------------------------------------

BASE_FROM = (
    CODES_FOREST
    + CODES_TTCE
    + CODES_TTP
    + CODES_TTA
    + CODES_TTW
    + CODES_OTH
    + CODES_PARENT
)


BASE_TO = (
    [OUT['TTF']] * len(CODES_FOREST)
    + [OUT['TTCe']] * len(CODES_TTCE)
    + [OUT['TTP']] * len(CODES_TTP)
    + [OUT['TTA']] * len(CODES_TTA)
    + [OUT['TTW']] * len(CODES_TTW)
    + [OUT['OTH']] * len(CODES_OTH)
    + [OUT['OTH']] * len(CODES_PARENT)
)


# QA note:
# unexpected observed codes are flagged by unknown_class QA, but final
# classification follows the original JS behavior and keeps them as OTH.
UNMAPPED_SENTINEL = 255  # retained only as a legacy/debug constant


# ==============================================================================
# 4. FIXED OUTPUT GRID
# ==============================================================================

# Requested CRS.
OUTPUT_CRS = 'EPSG:4326'


# EPSG:4326 is angular, so no fixed degree cell is physically exactly
# 1 km everywhere. This is a NOMINAL 1000-m grid with a fixed global origin.
PIXEL_SIZE_DEG = (
    1000.0 / 111319.49079327357
)


# [xScale, xShear, xOrigin, yShear, yScale, yOrigin]
OUTPUT_TRANSFORM = [
    PIXEL_SIZE_DEG,
    0,
    -180,
    0,
    -PIXEL_SIZE_DEG,
    90,
]


# Same export extent for every year.
EXPORT_REGION = (
    lulc
    .select('classification_1985')
    .geometry()
    .bounds()
)


# ==============================================================================
# 5. STABLE 30-m DOMAIN
# ==============================================================================

# Domain = union of source masks across 1985-2019.
#
# This is intentionally independent of whether the annual value is class 27.
# Therefore class 27 can lower annual completeness inside the stable domain.

YEAR_BANDS = [
    f'classification_{year}'
    for year in range(
        START_YEAR,
        END_YEAR + 1,
    )
]


DOMAIN_30M = (
    lulc
    .select(YEAR_BANDS)
    .mask()
    .reduce(
        ee.Reducer.max()
    )
    .gt(0)
    .selfMask()
    .rename('domain_30m')
)


# ==============================================================================
# 6. HELPERS
# ==============================================================================

def is_in_codes(
    image,
    codes,
):
    return (
        image
        .remap(
            codes,
            [1] * len(codes),
            0,
        )
        .eq(1)
    )


def strict_base_reclass(
    lulc_year,
):
    """
    JS-compatible base reclassification.

    Every OBSERVED MapBiomas code starts as OTH, matching the original
    JavaScript rule:

        output = lulcYear * 0 + OUT.OTH

    Then known forest / savanna / pasture / agriculture / water classes
    overwrite OTH.

    Class 27 ("Nao Observado") is handled separately as MISSING and masked
    from the final annual classification.

    Unknown observed codes remain OTH in the final product, but are flagged
    separately by QA so legend surprises are visible rather than silent.
    """

    output = (
        lulc_year
        .multiply(0)
        .add(
            OUT['OTH']
        )
        .toUint16()
    )

    output = output.where(
        is_in_codes(
            lulc_year,
            CODES_FOREST,
        ),
        OUT['TTF'],
    )

    output = output.where(
        is_in_codes(
            lulc_year,
            CODES_TTCE,
        ),
        OUT['TTCe'],
    )

    output = output.where(
        is_in_codes(
            lulc_year,
            CODES_TTP,
        ),
        OUT['TTP'],
    )

    output = output.where(
        is_in_codes(
            lulc_year,
            CODES_TTA,
        ),
        OUT['TTA'],
    )

    output = output.where(
        is_in_codes(
            lulc_year,
            CODES_TTW,
        ),
        OUT['TTW'],
    )

    return output


def zero_like(
    reference,
):
    """
    Explicit zero image without preserving a restricted ancillary footprint.
    """
    return (
        reference
        .multiply(0)
        .unmask(
            0,
            False,
        )
        .toByte()
    )


# ==============================================================================
# 6B. TARGET-YEAR -> SOURCE-YEAR POLICY
# ==============================================================================

def source_year_policy(target_year):
    """
    Return the source year used by each annual input for a target output year.

    1979-1984:
        LULC       -> 1985
        edge       -> 1985
        fire       -> 1985
        secondary  -> 1987
        logging    -> 1988

    1985:
        LULC/edge/fire -> 1985
        secondary     -> 1987
        logging       -> 1988

    1986:
        LULC/edge/fire -> 1986
        secondary     -> 1987
        logging       -> 1988

    1987:
        LULC/edge/fire/secondary -> 1987
        logging                  -> 1988

    1988-2019:
        matching target year for all inputs.
    """

    target_year = int(target_year)

    if (
        target_year < FINAL_START_YEAR
        or target_year > FINAL_END_YEAR
    ):
        raise ValueError(
            f'Target year {target_year} is outside '
            f'{FINAL_START_YEAR}-{FINAL_END_YEAR}.'
        )

    lulc_source_year = max(
        target_year,
        START_YEAR,
    )

    edge_source_year = max(
        target_year,
        START_YEAR,
    )

    fire_source_year = max(
        target_year,
        START_YEAR,
    )

    secondary_source_year = max(
        target_year,
        SECONDARY_FALLBACK_YEAR,
    )

    logging_source_year = max(
        target_year,
        LOGGING_FALLBACK_YEAR,
    )

    return {
        'target_year':
            target_year,

        'lulc_source_year':
            lulc_source_year,

        'edge_source_year':
            edge_source_year,

        'fire_source_year':
            fire_source_year,

        'secondary_source_year':
            secondary_source_year,

        'logging_source_year':
            logging_source_year,
    }


# ==============================================================================
# 7. STEP 1 — BUILD ONE ANNUAL CATEGORICAL MAP
# ==============================================================================

def build_year(
    year,
):

    year = int(year)

    source_years = (
        source_year_policy(
            year
        )
    )

    lulc_source_year = (
        source_years[
            'lulc_source_year'
        ]
    )

    edge_source_year = (
        source_years[
            'edge_source_year'
        ]
    )

    fire_source_year = (
        source_years[
            'fire_source_year'
        ]
    )

    secondary_source_year = (
        source_years[
            'secondary_source_year'
        ]
    )

    logging_source_year = (
        source_years[
            'logging_source_year'
        ]
    )


    # --------------------------------------------------------------------------
    # LULC for this target year.
    #
    # For target 1979-1984, classification_1985 is used as the proxy.
    # --------------------------------------------------------------------------

    lulc_year = (
        lulc
        .select(
            f'classification_{lulc_source_year}'
        )
        .rename(
            f'lulc_{year}'
        )
    )


    # --------------------------------------------------------------------------
    # Source footprint / mask.
    # --------------------------------------------------------------------------

    source_mask = (
        lulc_year
        .mask()
        .gt(0)
        .unmask(
            0,
            False,
        )
    )


    # --------------------------------------------------------------------------
    # Base map.
    #
    # JS-compatible behavior:
    #   every observed non-27 source code is assigned to one of the 8 outputs;
    #   unexpected codes default to OTH.
    # --------------------------------------------------------------------------

    base_raw = (
        strict_base_reclass(
            lulc_year
        )
    )


    # --------------------------------------------------------------------------
    # Observed / valid source pixel.
    #
    # The only MapBiomas legend value explicitly treated as missing is 27
    # ("Nao Observado"), plus native source mask gaps.
    # --------------------------------------------------------------------------

    observed = (
        source_mask
        .And(
            lulc_year
            .unmask(
                CODE_NOT_OBSERVED,
                False,
            )
            .neq(
                CODE_NOT_OBSERVED
            )
        )
    )


    valid_class = (
        observed
        .rename(
            f'valid_class_{year}'
        )
        .toByte()
    )


    # --------------------------------------------------------------------------
    # Unexpected observed codes.
    #
    # IMPORTANT:
    # They are QA-FLAGGED but remain valid OTH pixels in the final output,
    # matching the original JavaScript "default OTH" behavior.
    # --------------------------------------------------------------------------

    known_codes = (
        BASE_FROM
        + [CODE_NOT_OBSERVED]
    )

    unknown_class = (
        observed
        .And(
            is_in_codes(
                lulc_year,
                known_codes,
            )
            .Not()
            .unmask(
                0,
                False,
            )
        )
        .rename(
            f'unknown_class_{year}'
        )
        .toByte()
    )


    # --------------------------------------------------------------------------
    # Hierarchical code QA.
    # --------------------------------------------------------------------------

    parent_class_present = (
        is_in_codes(
            lulc_year,
            CODES_PARENT,
        )
        .unmask(
            0,
            False,
        )
        .And(
            source_mask
        )
        .rename(
            f'parent_class_{year}'
        )
        .toByte()
    )


    # --------------------------------------------------------------------------
    # Base reclassification.
    # --------------------------------------------------------------------------

    base = (
        base_raw
        .updateMask(
            valid_class
        )
        .rename(
            f'base_{year}'
        )
        .toByte()
    )


    # --------------------------------------------------------------------------
    # Forest base.
    # --------------------------------------------------------------------------

    forest_base = (
        is_in_codes(
            lulc_year,
            CODES_FOREST,
        )
        .unmask(
            0,
            False,
        )
        .And(
            valid_class
        )
        .rename(
            f'forest_base_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # SECONDARY VEGETATION
    #
    # PRECEDENCE #1
    # ==========================================================================

    # Source year comes from source_year_policy().
    #
    # 1979-1986 -> secondary_1987
    # 1987 onward -> matching annual secondary band.


    secondary_raw = (
        is_in_codes(
            secondary
            .select(
                f'classification_{secondary_source_year}'
            ),
            CODES_SECONDARY,
        )
        .unmask(
            0,
            False,
        )
        .And(
            valid_class
        )
    )


    secondary_raw = (
        secondary_raw
        .rename(
            f'secondary_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # EDGE
    # ==========================================================================

    edge_distance = (
        edge
        .select(
            f'edge_{edge_source_year}'
        )
        .rename(
            f'edge_distance_{year}'
        )
    )


    # Threshold BEFORE unmask.
    edge_raw = (
        edge_distance
        .lte(
            EDGE_THRESHOLD_M
        )
        .unmask(
            0,
            False,
        )
        .And(
            valid_class
        )
        .rename(
            f'edge_raw_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # FIRE
    # ==========================================================================

    fire_raw = (
        fire
        .select(
            f'burned_area_{fire_source_year}'
        )
        .eq(1)
        .unmask(
            0,
            False,
        )
        .And(
            valid_class
        )
        .rename(
            f'fire_raw_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # LOGGING
    #
    # The product begins in 1988.
    #
    # Temporal handling:
    #   1985 -> logging_1988 proxy
    #   1986 -> logging_1988 proxy
    #   1987 -> logging_1988 proxy
    #   1988 onward -> matching annual logging band
    #
    # Spatial handling:
    #   logging only covers Legal Amazon.
    #   Outside its source footprint logging contribution = 0,
    #   so it MUST NOT mask edge/fire elsewhere.
    # ==========================================================================

    # Source year comes from source_year_policy().
    #
    # 1979-1987 -> logging_1988
    # 1988 onward -> matching annual logging band.


    logging_raw = (
        logging
        .select(
            f'logging_{logging_source_year}'
        )
        .eq(1)
        .unmask(
            0,
            False,
        )
        .And(
            valid_class
        )
        .rename(
            f'logging_raw_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # COMBINED DEGRADATION
    # ==========================================================================

    degradation_raw = (
        edge_raw
        .unmask(
            0,
            False,
        )
        .Or(
            fire_raw
            .unmask(
                0,
                False,
            )
        )
        .Or(
            logging_raw
            .unmask(
                0,
                False,
            )
        )
        .And(
            valid_class
        )
        .rename(
            f'degradation_raw_{year}'
        )
        .toByte()
    )


    degradation_forest = (
        degradation_raw
        .And(
            forest_base
        )
        .rename(
            f'degradation_forest_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # TTS / DEGRADATION OVERLAP QA
    #
    # secondary
    # AND degradation
    # AND forest base
    # ==========================================================================

    overlap = (
        secondary_raw
        .And(
            degradation_raw
        )
        .And(
            forest_base
        )
        .rename(
            f'secondary_degradation_overlap_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # FINAL FOREST STATES
    # ==========================================================================

    tts = (
        secondary_raw
        .rename(
            f'TTS_mask_{year}'
        )
        .toByte()
    )


    ttfd = (
        forest_base
        .And(
            degradation_raw
        )
        .And(
            tts.Not()
        )
        .rename(
            f'TTFd_mask_{year}'
        )
        .toByte()
    )


    ttf = (
        forest_base
        .And(
            degradation_raw.Not()
        )
        .And(
            tts.Not()
        )
        .rename(
            f'TTF_mask_{year}'
        )
        .toByte()
    )


    # ==========================================================================
    # FINAL CATEGORICAL MAP
    #
    # TTFd written first.
    # TTS written LAST.
    # ==========================================================================

    final = (
        base
        .where(
            ttfd,
            OUT['TTFd'],
        )
        .where(
            tts,
            OUT['TTS'],
        )
        .updateMask(
            valid_class
        )
        .rename(
            f'classification_{year}'
        )
        .toByte()
        .set({
            'year':
                year,

            'lulc_source_year':
                lulc_source_year,

            'edge_source_year':
                edge_source_year,

            'fire_source_year':
                fire_source_year,

            'secondary_source_year':
                secondary_source_year,

            'logging_source_year':
                logging_source_year,

            'precedence':
                'TTS > TTFd > TTF',

            'edge_threshold_m':
                EDGE_THRESHOLD_M,

            'mapbiomas_collection':
                'Brazil Collection 10.1',

            'secondary_temporal_handling':
                (
                    '1979-1986 use classification_1987 from the secondary '
                    'vegetation product as a temporal proxy; 1987 onward '
                    'uses the matching annual secondary band.'
                ),

            'logging_temporal_handling':
                (
                    '1979-1987 use logging_1988 as a temporal proxy; '
                    '1988 onward uses the matching annual logging band.'
                ),

            'not_observed_handling':
                'class 27 treated as missing',

            'logging_coverage_note':
                (
                    'Logging covers Legal Amazon; outside its footprint '
                    'logging contributes zero and does not mask edge/fire.'
                ),
        })
    )


    return {

        'year':
            year,

        'lulcSourceYear':
            lulc_source_year,

        'edgeSourceYear':
            edge_source_year,

        'fireSourceYear':
            fire_source_year,

        'secondarySourceYear':
            secondary_source_year,

        'loggingSourceYear':
            logging_source_year,

        'lulc':
            lulc_year,

        'validClass':
            valid_class,

        'unknownClass':
            unknown_class,

        'parentClassPresent':
            parent_class_present,

        'base':
            base,

        'forestBase':
            forest_base,

        'secondary':
            secondary_raw,

        'secondarySourceYear':
            secondary_source_year,

        'edgeRaw':
            edge_raw,

        'fireRaw':
            fire_raw,

        'loggingRaw':
            logging_raw,

        'degradationRaw':
            degradation_raw,

        'degradation':
            degradation_forest,

        'overlap':
            overlap,

        'TTF':
            ttf,

        'TTFd':
            ttfd,

        'TTS':
            tts,

        'final':
            final,
    }


# ==============================================================================
# 8. STEP 2 — CATEGORICAL -> 8-BAND ONE-HOT 30 m
# ==============================================================================

def categorical_to_one_hot(
    class_image,
    year,
):

    class_image = (
        ee.Image(
            class_image
        )
    )


    # .eq() preserves the class-image mask.
    #
    # Valid pixel:
    #   one band = 1
    #   seven = 0
    #
    # Missing pixel:
    #   all eight remain masked.

    one_hot = (
        ee.Image
        .cat([

            class_image
            .eq(
                OUT['TTF']
            ),

            class_image
            .eq(
                OUT['TTFd']
            ),

            class_image
            .eq(
                OUT['TTS']
            ),

            class_image
            .eq(
                OUT['TTCe']
            ),

            class_image
            .eq(
                OUT['TTP']
            ),

            class_image
            .eq(
                OUT['TTA']
            ),

            class_image
            .eq(
                OUT['TTW']
            ),

            class_image
            .eq(
                OUT['OTH']
            ),
        ])

        .rename(
            FRACTION_BANDS
        )

        .toFloat()

        .updateMask(
            DOMAIN_30M
        )

        .set({
            'year':
                int(year),

            'representation':
                'one_hot_30m',

            'band_order':
                ','.join(
                    FRACTION_BANDS
                ),
        })
    )


    return one_hot


# ==============================================================================
# 9. STEP 5 — COMPLETENESS AT 30 m
# ==============================================================================

def make_completeness_30m(
    valid_class,
):

    # 1:
    #   annual classification exists and is usable.
    #
    # 0:
    #   masked / class 27 / unexpected class.
    #
    # Outside stable MapBiomas domain:
    #   masked.

    return (
        ee.Image(
            valid_class
        )
        .unmask(
            0,
            False,
        )
        .updateMask(
            DOMAIN_30M
        )
        .rename(
            'completeness'
        )
        .toFloat()
    )


# ==============================================================================
# 10. STEP 3 — BUILD MATERIALIZABLE 1-km PRODUCT
# ==============================================================================

def build_intermediate_1km(
    year,
):

    result = (
        build_year(
            year
        )
    )


    one_hot = (
        categorical_to_one_hot(
            result['final'],
            year,
        )
    )


    completeness = (
        make_completeness_30m(
            result['validClass']
        )
    )


    # --------------------------------------------------------------------------
    # 9 FINAL SOURCE BANDS.
    #
    # Fractions:
    #   missing 30-m pixels are masked.
    #
    # Completeness:
    #   missing 30-m pixels are explicit zero.
    # --------------------------------------------------------------------------

    source_9 = (
        one_hot
        .addBands(
            completeness
        )
        .select(
            FINAL_BANDS
        )
    )


    # --------------------------------------------------------------------------
    # FRACTION / COMPLETENESS AGGREGATION.
    #
    # Mean applied independently to every band.
    #
    # NO:
    #   mode
    #   majority
    #   smoothing
    #   resample
    # --------------------------------------------------------------------------

    fractions_9 = (
        source_9
        .reduceResolution(

            reducer=
                ee.Reducer.mean(),

            bestEffort=
                False,

            maxPixels=
                1600,
        )
        .select(
            FINAL_BANDS
        )
        .toFloat()
    )


    # --------------------------------------------------------------------------
    # INTERNAL QA SOURCE BANDS.
    #
    # Explicit 0/1 within stable 30-m domain.
    # --------------------------------------------------------------------------

    qa_source = (
        ee.Image
        .cat([

            result['forestBase']
            .unmask(
                0,
                False,
            )
            .updateMask(
                DOMAIN_30M
            )
            .rename(
                'forest_base_count'
            ),

            result['overlap']
            .unmask(
                0,
                False,
            )
            .updateMask(
                DOMAIN_30M
            )
            .rename(
                'secondary_degradation_overlap_count'
            ),

            result['unknownClass']
            .unmask(
                0,
                False,
            )
            .updateMask(
                DOMAIN_30M
            )
            .rename(
                'unknown_class_count'
            ),

            result['parentClassPresent']
            .unmask(
                0,
                False,
            )
            .updateMask(
                DOMAIN_30M
            )
            .rename(
                'parent_class_count'
            ),
        ])
        .toFloat()
    )


    # Weighted sum gives pixel-equivalent counts.
    qa_counts = (
        qa_source
        .reduceResolution(

            reducer=
                ee.Reducer.sum(),

            bestEffort=
                False,

            maxPixels=
                1600,
        )
        .select(
            QA_COUNT_BANDS
        )
        .toFloat()
    )


    return (
        fractions_9

        .addBands(
            qa_counts
        )

        .select(
            INTERMEDIATE_BANDS
        )

        .set({

            'year':
                int(year),

            'source_year':
                int(result['lulcSourceYear']),

            'lulc_source_year':
                int(result['lulcSourceYear']),

            'edge_source_year':
                int(result['edgeSourceYear']),

            'fire_source_year':
                int(result['fireSourceYear']),

            'secondary_source_year':
                int(result['secondarySourceYear']),

            'logging_source_year':
                int(result['loggingSourceYear']),

            'source_resolution_m':
                30,

            'target_resolution_nominal_m':
                1000,

            'output_crs':
                OUTPUT_CRS,

            'output_transform':
                json.dumps(
                    OUTPUT_TRANSFORM
                ),

            'fraction_aggregation':
                'bandwise arithmetic mean',

            'qa_count_aggregation':
                'bandwise weighted sum',

            'completeness_threshold':
                COMPLETENESS_THRESHOLD,

            'band_order_final':
                ','.join(
                    FINAL_BANDS
                ),
        })
    )


# ==============================================================================
# 11. EARTH ENGINE ASSET HELPERS
# ==============================================================================

def ensure_asset_folder(
    folder_id,
):

    try:

        ee.data.getAsset(
            folder_id
        )

        print(
            'Asset folder exists:',
            folder_id,
        )

    except Exception:

        print(
            'Creating asset folder:',
            folder_id,
        )

        ee.data.createAsset(
            {
                'type':
                    'FOLDER'
            },
            folder_id,
        )


def intermediate_asset_id(
    year,
):

    return (
        f'{INTERMEDIATE_ASSET_ROOT}/'
        f'fractional_1km_{int(year)}'
    )


def asset_exists(
    asset_id,
):

    try:

        ee.data.getAsset(
            asset_id
        )

        return True

    except Exception:

        return False


# ==============================================================================
# 12. PHASE A — EXPORT 1979-2019 TO EE ASSETS
# ==============================================================================

def create_phase_a_tasks():

    ensure_asset_folder(
        INTERMEDIATE_ASSET_ROOT
    )


    tasks = []


    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        asset_id = (
            intermediate_asset_id(
                year
            )
        )


        if (
            asset_exists(
                asset_id
            )
        ):

            print(
                'Skip existing:',
                asset_id,
            )

            continue


        image = (
            build_intermediate_1km(
                year
            )
        )


        task = (
            ee.batch.Export.image
            .toAsset(

                image=
                    image,

                description=
                    f'mapbiomas_fractional_1km_{year}',

                assetId=
                    asset_id,

                region=
                    EXPORT_REGION,

                crs=
                    OUTPUT_CRS,

                crsTransform=
                    OUTPUT_TRANSFORM,

                maxPixels=
                    1e10,

                pyramidingPolicy={
                    '.default':
                        'mean'
                },
            )
        )


        tasks.append(
            (
                year,
                task,
            )
        )


    return tasks


def start_tasks(
    tasks,
):

    # Start all.
    #
    # Earth Engine manages READY / RUNNING concurrency server-side.
    # Once submitted, tasks continue even if Colab disconnects.

    for year, task in tasks:

        task.start()

        print(
            f'Started {year}:',
            task.id,
        )


    print(
        'Submitted tasks:',
        len(tasks),
    )


def print_task_status(
    tasks,
):

    for year, task in tasks:

        status = (
            task.status()
        )

        print(
            year,
            status.get(
                'state'
            ),
            status.get(
                'error_message',
                '',
            ),
            task.id,
        )


# ==============================================================================
# 13. PHASE B — LOAD MATERIALIZED PRODUCTS
# ==============================================================================

def check_all_intermediate_assets():

    missing = []


    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        asset_id = (
            intermediate_asset_id(
                year
            )
        )


        if not asset_exists(
            asset_id
        ):

            missing.append(
                asset_id
            )


    if missing:

        message = (
            f'{len(missing)} intermediate assets are missing. '
            f'First missing asset: {missing[0]}'
        )


        if STRICT_ASSET_CHECK:

            raise RuntimeError(
                message
            )


        print(
            'WARNING:',
            message,
        )


    return missing


def load_final_products():

    products = {}


    # All 41 target years are explicitly materialized in Phase A.
    #
    # For 1979-1984 those assets were built with:
    #
    #   LULC       = 1985
    #   edge       = 1985
    #   fire       = 1985
    #   secondary  = 1987
    #   logging    = 1988
    #
    # Therefore no hidden post-hoc copying occurs in Phase B.

    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        products[
            year
        ] = (

            ee.Image(
                intermediate_asset_id(
                    year
                )
            )

            .select(
                INTERMEDIATE_BANDS
            )
        )


    return products


# ==============================================================================
# 14. FINAL QA ON MATERIALIZED 1-km ASSETS
# ==============================================================================

def annual_qa_from_materialized(
    product,
    year,
):

    product = (
        ee.Image(
            product
        )
    )


    # --------------------------------------------------------------------------
    # Sum of the eight fractions.
    #
    # CRITICAL:
    # Use ordinary image arithmetic rather than Image.reduce(Reducer.sum()).
    # The latter can interact with fractional masks/weights and previously
    # produced spurious values such as 1/255.
    # --------------------------------------------------------------------------

    sum8 = (
        product.select('TTF')
        .add(
            product.select('TTFd')
        )
        .add(
            product.select('TTS')
        )
        .add(
            product.select('TTCe')
        )
        .add(
            product.select('TTP')
        )
        .add(
            product.select('TTA')
        )
        .add(
            product.select('TTW')
        )
        .add(
            product.select('OTH')
        )
        .rename(
            'sum8'
        )
    )


    # --------------------------------------------------------------------------
    # Absolute compositional error.
    # --------------------------------------------------------------------------

    abs_error = (

        sum8

        .subtract(1)

        .abs()

        .rename(
            'abs_error'
        )
    )


    # --------------------------------------------------------------------------
    # Low-completeness flag.
    # --------------------------------------------------------------------------

    low_completeness = (

        product

        .select(
            'completeness'
        )

        .lt(
            COMPLETENESS_THRESHOLD
        )

        .rename(
            'low_completeness'
        )

        .toFloat()
    )


    # --------------------------------------------------------------------------
    # Cell-level QA.
    # --------------------------------------------------------------------------

    qa_image = (
        ee.Image.cat([

            sum8,

            abs_error,

            low_completeness,

            product
            .select(
                'completeness'
            ),
        ])
    )


    reducer = (

        ee.Reducer.min()

        .combine(
            ee.Reducer.max(),
            sharedInputs=
                True,
        )

        .combine(
            ee.Reducer.mean(),
            sharedInputs=
                True,
        )
    )


    stats = (

        qa_image

        .reduceRegion(

            reducer=
                reducer,

            geometry=
                EXPORT_REGION,

            crs=
                OUTPUT_CRS,

            crsTransform=
                OUTPUT_TRANSFORM,

            maxPixels=
                1e9,

            tileScale=
                8,
        )

        .getInfo()
    )


    # --------------------------------------------------------------------------
    # Overlap / class-QA counts.
    #
    # Cheap because this is now already materialized at 1 km.
    # --------------------------------------------------------------------------

    count_stats = (

        product

        .select(
            QA_COUNT_BANDS
        )

        .reduceRegion(

            reducer=
                ee.Reducer.sum(),

            geometry=
                EXPORT_REGION,

            crs=
                OUTPUT_CRS,

            crsTransform=
                OUTPUT_TRANSFORM,

            maxPixels=
                1e9,

            tileScale=
                8,
        )

        .getInfo()
    )


    forest_count = float(

        count_stats.get(
            'forest_base_count'
        )
        or 0.0
    )


    overlap_count = float(

        count_stats.get(
            'secondary_degradation_overlap_count'
        )
        or 0.0
    )


    overlap_fraction = (

        overlap_count /
        forest_count

        if forest_count > 0

        else 0.0
    )


    abs_error_max = float(

        stats.get(
            'abs_error_max'
        )
        or 0.0
    )


    low_fraction = float(

        stats.get(
            'low_completeness_mean'
        )
        or 0.0
    )


    source_years = (
        source_year_policy(
            year
        )
    )


    return {

        'year':
            int(year),

        'source_year':
            int(
                source_years[
                    'lulc_source_year'
                ]
            ),

        'lulc_source_year':
            int(
                source_years[
                    'lulc_source_year'
                ]
            ),

        'edge_source_year':
            int(
                source_years[
                    'edge_source_year'
                ]
            ),

        'fire_source_year':
            int(
                source_years[
                    'fire_source_year'
                ]
            ),

        'secondary_source_year':
            int(
                source_years[
                    'secondary_source_year'
                ]
            ),

        'logging_source_year':
            int(
                source_years[
                    'logging_source_year'
                ]
            ),


        # ----------------------------------------------------------------------
        # Sum of fractions.
        # ----------------------------------------------------------------------

        'sum8_min':
            stats.get(
                'sum8_min'
            ),

        'sum8_max':
            stats.get(
                'sum8_max'
            ),

        'sum8_mean':
            stats.get(
                'sum8_mean'
            ),

        'max_absolute_sum_error':
            abs_error_max,

        'sum_qc_tolerance':
            SUM_TOLERANCE,

        'sum_qc_pass':
            (
                abs_error_max <=
                SUM_TOLERANCE
            ),


        # ----------------------------------------------------------------------
        # Completeness.
        # ----------------------------------------------------------------------

        'completeness_min':
            stats.get(
                'completeness_min'
            ),

        'completeness_max':
            stats.get(
                'completeness_max'
            ),

        'completeness_mean':
            stats.get(
                'completeness_mean'
            ),

        'low_completeness_fraction':
            low_fraction,

        'low_completeness_percent':
            (
                low_fraction *
                100.0
            ),

        'completeness_threshold':
            COMPLETENESS_THRESHOLD,


        # ----------------------------------------------------------------------
        # TTS / degradation overlap.
        # ----------------------------------------------------------------------

        'forest_base_pixel_equivalents':
            forest_count,

        'secondary_degradation_overlap_pixel_equivalents':
            overlap_count,

        'secondary_degradation_overlap_fraction_of_forest':
            overlap_fraction,

        'secondary_degradation_overlap_percent_of_forest':
            (
                overlap_fraction *
                100.0
            ),

        'overlap_gt_2pct':
            (
                overlap_fraction >
                0.02
            ),

        'overlap_gt_3pct':
            (
                overlap_fraction >
                0.03
            ),


        # ----------------------------------------------------------------------
        # Legend QA.
        # ----------------------------------------------------------------------

        'unknown_class_pixel_equivalents':
            float(
                count_stats.get(
                    'unknown_class_count'
                )
                or 0.0
            ),

        'parent_class_pixel_equivalents':
            float(
                count_stats.get(
                    'parent_class_count'
                )
                or 0.0
            ),
    }


def run_full_qa(
    products,
):

    rows = []


    # Sequential client requests avoid:
    #
    # "Too many concurrent aggregations"

    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        print(
            f'QA {year} ...'
        )


        row = (
            annual_qa_from_materialized(

                products[
                    year
                ],

                year,
            )
        )


        rows.append(
            row
        )


        print(
            '  '
            f"sum=[{row['sum8_min']}, {row['sum8_max']}], "
            f"max_error={row['max_absolute_sum_error']}, "
            f"low_complete={row['low_completeness_percent']:.3f}%, "
            f"overlap="
            f"{row['secondary_degradation_overlap_percent_of_forest']:.3f}%"
        )


    df = (
        pd.DataFrame(
            rows
        )
    )


    qa_csv = (
        '/content/'
        'MapBiomas_fractional_QA_1979_2019.csv'
    )


    df.to_csv(
        qa_csv,
        index=
            False,
    )


    return (
        df,
        qa_csv,
    )


# ==============================================================================
# 15. FINAL PRIMARY GeoTIFF EXPORTS
#
# 41 files:
#   1979 ... 2019
#
# Each file:
#   9 bands
#
#   TTF
#   TTFd
#   TTS
#   TTCe
#   TTP
#   TTA
#   TTW
#   OTH
#   completeness
# ==============================================================================

def make_primary_export_task(
    product,
    year,
):

    source_years = (
        source_year_policy(
            year
        )
    )


    image = (

        ee.Image(
            product
        )

        .select(
            FINAL_BANDS
        )

        .toFloat()

        .set({

            'year':
                int(year),

            'source_year':
                int(
                    source_years[
                        'lulc_source_year'
                    ]
                ),

            'lulc_source_year':
                int(
                    source_years[
                        'lulc_source_year'
                    ]
                ),

            'edge_source_year':
                int(
                    source_years[
                        'edge_source_year'
                    ]
                ),

            'fire_source_year':
                int(
                    source_years[
                        'fire_source_year'
                    ]
                ),

            'secondary_source_year':
                int(
                    source_years[
                        'secondary_source_year'
                    ]
                ),

            'logging_source_year':
                int(
                    source_years[
                        'logging_source_year'
                    ]
                ),

            'band_order':
                ','.join(
                    FINAL_BANDS
                ),

            'low_completeness_threshold':
                COMPLETENESS_THRESHOLD,

            'unexpected_class_handling':
                'default OTH + QA flag',

            'not_observed_handling':
                'class 27 = missing',
        })
    )


    description = (
        f'MapBiomas_fractional_1km_{year}'
    )


    filename = (
        f'MapBiomas_fractional_1km_{year}'
    )


    common = dict(

        image=
            image,

        description=
            description,

        region=
            EXPORT_REGION,

        crs=
            OUTPUT_CRS,

        crsTransform=
            OUTPUT_TRANSFORM,

        maxPixels=
            1e10,

        fileFormat=
            'GeoTIFF',

        formatOptions={
            'cloudOptimized':
                True,

            'noData':
                -9999,
        },
    )


    if (
        EXPORT_DESTINATION
        .upper()
        ==
        'GCS'
    ):

        return (
            ee.batch.Export.image
            .toCloudStorage(

                bucket=
                    GCS_BUCKET,

                fileNamePrefix=
                    (
                        f'{GCS_PREFIX}/'
                        f'{filename}'
                    ),

                **common,
            )
        )


    return (
        ee.batch.Export.image
        .toDrive(

            folder=
                DRIVE_FOLDER,

            fileNamePrefix=
                filename,

            **common,
        )
    )


def create_primary_export_tasks(
    products,
):

    tasks = []


    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        task = (
            make_primary_export_task(

                products[
                    year
                ],

                year,
            )
        )


        tasks.append(
            (
                year,
                task,
            )
        )


    return tasks


# ==============================================================================
# 16. LOW-COMPLETENESS DELIVERY MASK
#
# One additional 41-band GeoTIFF:
#
#   low_1979
#   ...
#   low_2019
#
# Value:
#   1 = completeness < 0.90
#   0 = completeness >= 0.90
# ==============================================================================

def make_low_completeness_stack(
    products,
):

    bands = []


    for year in range(
        FINAL_START_YEAR,
        FINAL_END_YEAR + 1,
    ):

        band = (

            ee.Image(
                products[
                    year
                ]
            )

            .select(
                'completeness'
            )

            .lt(
                COMPLETENESS_THRESHOLD
            )

            .rename(
                f'low_{year}'
            )

            .toByte()
        )


        bands.append(
            band
        )


    return (
        ee.Image.cat(
            bands
        )
    )


def make_low_completeness_export_task(
    products,
):

    image = (
        make_low_completeness_stack(
            products
        )
    )


    common = dict(

        image=
            image,

        description=
            'MapBiomas_low_completeness_1979_2019',

        region=
            EXPORT_REGION,

        crs=
            OUTPUT_CRS,

        crsTransform=
            OUTPUT_TRANSFORM,

        maxPixels=
            1e10,

        fileFormat=
            'GeoTIFF',

        formatOptions={
            'cloudOptimized':
                True,

            'noData':
                255,
        },
    )


    if (
        EXPORT_DESTINATION
        .upper()
        ==
        'GCS'
    ):

        return (

            ee.batch.Export.image
            .toCloudStorage(

                bucket=
                    GCS_BUCKET,

                fileNamePrefix=
                    (
                        f'{GCS_PREFIX}/'
                        'MapBiomas_low_completeness_1979_2019'
                    ),

                **common,
            )
        )


    return (

        ee.batch.Export.image
        .toDrive(

            folder=
                DRIVE_FOLDER,

            fileNamePrefix=
                'MapBiomas_low_completeness_1979_2019',

            **common,
        )
    )


# ==============================================================================
# 17. METADATA FILES
# ==============================================================================

def write_metadata_files():

    processing_date = (
        datetime
        .now(
            timezone.utc
        )
        .isoformat()
    )


    metadata = {

        'dataset_name':
            (
                'MapBiomas annual fractional '
                'land-cover composition'
            ),

        'temporal_range':
            '1979-2019',

        'native_mapbiomas_range':
            '1985-2019',

        'temporal_extension_1979_1984':
            (
                'Each target year 1979-1984 is explicitly constructed using '
                'LULC_1985, edge_1985, burned_area_1985, '
                'secondary classification_1987 and logging_1988. Because '
                '1985 uses the same source-year combination for these inputs, '
                '1979-1985 are expected to be identical under this proxy rule.'
            ),

        'mapbiomas_collection':
            'Brazil Collection 10.1',

        'mapbiomas_lulc_asset':
            ASSET_LULC,

        'secondary_vegetation_asset':
            ASSET_SECONDARY,

        'edge_degradation_asset':
            ASSET_EDGE,

        'logging_asset':
            ASSET_LOGGING,

        'fire_asset':
            ASSET_FIRE,

        'secondary_vegetation_rule':
            (
                'Secondary flag = classification_SOURCE_YEAR in {3,5}. '
                'For 1985-1986, SOURCE_YEAR=1987; for 1987-2019, '
                'SOURCE_YEAR=target year. TTS has precedence over TTFd.'
            ),

        'secondary_vegetation_temporal_proxy':
            (
                'The secondary-vegetation product begins in 1987. '
                'classification_1987 is used as the secondary proxy for '
                '1985 and 1986. Years 1979-1984 are exact copies of the '
                'finalized 1985 1-km product and therefore inherit this proxy.'
            ),

        'degradation_definition':
            (
                'edge_SOURCE_YEAR <= 150 m OR '
                'burned_area_SOURCE_YEAR == 1 OR '
                'logging_SOURCE_YEAR == 1. For targets 1979-1984, '
                'edge/fire SOURCE_YEAR=1985 and logging SOURCE_YEAR=1988. '
                'For targets 1985-1987 logging SOURCE_YEAR=1988. '
                'From 1988 onward all degradation drivers use the matching '
                'target year.'
            ),

        'logging_temporal_proxy':
            (
                'The logging product begins in 1988. logging_1988 is used '
                'as a temporal proxy for target years 1979-1987. '
                'From 1988 onward the matching annual logging band is used.'
            ),

        'logging_spatial_handling':
            (
                'Logging covers Legal Amazon. Outside its '
                'source footprint logging contributes 0 and '
                'does not mask edge or fire.'
            ),

        'precedence':
            'TTS > TTFd > TTF',

        'early_year_proxy_summary':
            (
                '1979-1984: LULC=1985, edge=1985, fire=1985, '
                'secondary=1987, logging=1988. '
                '1985: LULC/edge/fire=1985, secondary=1987, logging=1988. '
                '1986: LULC/edge/fire=1986, secondary=1987, logging=1988. '
                '1987: LULC/edge/fire/secondary=1987, logging=1988. '
                '1988-2019: matching annual source year for all inputs.'
            ),

        'forest_base_codes':
            CODES_FOREST,

        'not_observed_handling':
            (
                'MapBiomas class 27 (Nao Observado) is treated '
                'as missing rather than OTH.'
            ),

        'unexpected_class_handling':
            (
                'Observed source codes outside the explicit legend mapping '
                'remain valid and default to OTH, matching the original JS '
                'workflow; they are also reported by unknown-class QA.'
            ),

        'final_band_order':
            FINAL_BANDS,

        'aggregation':
            (
                '30-m one-hot class indicators -> 1-km bandwise '
                'arithmetic mean using Earth Engine reduceResolution(mean).'
            ),

        'missing_data_fraction_rule':
            (
                'Class fractions are calculated only over valid annual '
                '30-m classifications. Missing pixels are not redistributed.'
            ),

        'completeness_definition':
            (
                'Mean of the annual 30-m valid-class indicator within '
                'the stable MapBiomas spatial domain.'
            ),

        'completeness_threshold':
            COMPLETENESS_THRESHOLD,

        'low_completeness_delivery':
            (
                'Separate 41-band boolean GeoTIFF. '
                'Band low_YEAR = 1 where completeness < 0.90.'
            ),

        'output_crs':
            OUTPUT_CRS,

        'output_resolution_note':
            (
                'Nominal 1000-m grid represented in EPSG:4326. '
                'Because EPSG:4326 is angular, physical cell width '
                'varies with latitude.'
            ),

        'output_pixel_size_degrees':
            PIXEL_SIZE_DEG,

        'output_transform':
            OUTPUT_TRANSFORM,

        'processing_date_utc':
            processing_date,
    }


    metadata_json = (
        '/content/'
        'MapBiomas_fractional_metadata.json'
    )


    metadata_csv = (
        '/content/'
        'MapBiomas_fractional_metadata.csv'
    )


    with open(
        metadata_json,
        'w',
        encoding=
            'utf-8',
    ) as file:

        json.dump(
            metadata,
            file,
            indent=
                2,
            ensure_ascii=
                False,
        )


    # Serialize list/dict values for single-row CSV.
    csv_record = {}


    for key, value in metadata.items():

        if isinstance(
            value,
            (
                list,
                dict,
            ),
        ):

            csv_record[
                key
            ] = (
                json.dumps(
                    value,
                    ensure_ascii=
                        False,
                )
            )

        else:

            csv_record[
                key
            ] = value


    pd.DataFrame([
        csv_record
    ]).to_csv(
        metadata_csv,
        index=
            False,
    )


    return (
        metadata_json,
        metadata_csv,
    )


# ==============================================================================
# 18. OPTIONAL CELL INSPECTION
#
# Use only after Phase A asset exists.
#
# This avoids the projection mismatch you saw in the Code Editor because
# SUM_8 is calculated from the already-materialized 1-km asset.
# ==============================================================================

def inspect_materialized_cell(
    product,
    lon,
    lat,
):

    product = (
        ee.Image(
            product
        )
    )


    sum8 = (
        product.select('TTF')
        .add(
            product.select('TTFd')
        )
        .add(
            product.select('TTS')
        )
        .add(
            product.select('TTCe')
        )
        .add(
            product.select('TTP')
        )
        .add(
            product.select('TTA')
        )
        .add(
            product.select('TTW')
        )
        .add(
            product.select('OTH')
        )
        .rename(
            'SUM_8'
        )
    )


    abs_error = (

        sum8

        .subtract(1)

        .abs()

        .rename(
            'ABS_ERROR'
        )
    )


    inspect = (

        product

        .select(
            FINAL_BANDS
        )

        .addBands(
            sum8
        )

        .addBands(
            abs_error
        )
    )


    return (

        inspect

        .reduceRegion(

            reducer=
                ee.Reducer.first(),

            geometry=
                ee.Geometry.Point([
                    lon,
                    lat,
                ]),

            crs=
                OUTPUT_CRS,

            crsTransform=
                OUTPUT_TRANSFORM,

            maxPixels=
                100,
        )

        .getInfo()
    )


# ==============================================================================
# 19. EXECUTION
# ==============================================================================

phase_a_tasks = []


# ------------------------------------------------------------------------------
# PHASE A
# ------------------------------------------------------------------------------

if RUN_PHASE_A_CREATE_ASSETS:

    print(
        '--- PHASE A ---'
    )

    print(
        'Creating/submitting 1979-2019 intermediate 1-km assets.'
    )


    phase_a_tasks = (
        create_phase_a_tasks()
    )


    start_tasks(
        phase_a_tasks
    )


    print()

    print(
        'Phase A submitted.'
    )

    print(
        'Wait until ALL 41 tasks are COMPLETED.'
    )

    print(
        'Then rerun with Phase A off and Phase B flags on.'
    )


# ------------------------------------------------------------------------------
# PHASE B
# ------------------------------------------------------------------------------

if (
    RUN_PHASE_B_QA
    or
    RUN_PHASE_B_EXPORT_GEOTIFF
    or
    RUN_PHASE_B_EXPORT_LOW_COMPLETENESS_STACK
):

    print(
        '--- PHASE B ---'
    )


    check_all_intermediate_assets()


    products = (
        load_final_products()
    )


    # --------------------------------------------------------------------------
    # Metadata.
    # --------------------------------------------------------------------------

    (
        metadata_json,
        metadata_csv,
    ) = (
        write_metadata_files()
    )


    print(
        'Metadata written:'
    )

    print(
        metadata_json
    )

    print(
        metadata_csv
    )


    # --------------------------------------------------------------------------
    # QA.
    # --------------------------------------------------------------------------

    if RUN_PHASE_B_QA:

        print()

        print(
            'Running FINAL QA sequentially on materialized 1-km assets.'
        )


        (
            qa_df,
            qa_csv,
        ) = (
            run_full_qa(
                products
            )
        )


        print()

        print(
            'QA CSV:'
        )

        print(
            qa_csv
        )


        # Sum failures.
        failed_sum = (
            qa_df.loc[
                ~qa_df[
                    'sum_qc_pass'
                ]
            ]
        )


        if len(
            failed_sum
        ):

            print()

            print(
                'WARNING: sum-of-fractions QC failures:'
            )

            print(
                failed_sum[[
                    'year',
                    'max_absolute_sum_error',
                ]]
            )

        else:

            print()

            print(
                'All annual sum-of-fractions checks pass ±1e-6.'
            )


        # ----------------------------------------------------------------------
        # Practical release gate.
        # ----------------------------------------------------------------------

        hard_failures = (
            qa_df.loc[
                ~qa_df[
                    'sum_qc_pass'
                ]
            ]
        )

        if len(hard_failures) == 0:
            print()
            print(
                'HARD QA GATE: PASS '
                '(all annual fraction sums within tolerance).'
            )
        else:
            print()
            print(
                'HARD QA GATE: FAIL — inspect sum-of-fractions before release.'
            )


        # TTS/degradation overlap.
        high_overlap = (

            qa_df.loc[

                qa_df[
                    'secondary_degradation_overlap_fraction_of_forest'
                ]

                >
                0.02
            ]
        )


        if len(
            high_overlap
        ):

            print()

            print(
                'WARNING: TTS/degradation overlap > 2%:'
            )

            print(

                high_overlap[[

                    'year',

                    'secondary_degradation_overlap_percent_of_forest',
                ]]
            )


        # Unknown classes.
        unknown = (

            qa_df.loc[

                qa_df[
                    'unknown_class_pixel_equivalents'
                ]

                >
                0
            ]
        )


        if len(
            unknown
        ):

            print()

            print(
                'NOTE: unexpected MapBiomas classes found. '
                'They were retained as valid OTH pixels, matching the JS rule:'
            )

            print(

                unknown[[

                    'year',

                    'unknown_class_pixel_equivalents',
                ]]
            )


    # --------------------------------------------------------------------------
    # 41 annual primary GeoTIFFs.
    # --------------------------------------------------------------------------

    if RUN_PHASE_B_EXPORT_GEOTIFF:

        print()

        print(
            'Submitting 41 primary 9-band GeoTIFF exports.'
        )


        final_tasks = (
            create_primary_export_tasks(
                products
            )
        )


        start_tasks(
            final_tasks
        )


    # --------------------------------------------------------------------------
    # One 41-band low-completeness flag GeoTIFF.
    # --------------------------------------------------------------------------

    if (
        RUN_PHASE_B_EXPORT_LOW_COMPLETENESS_STACK
    ):

        print()

        print(
            'Submitting 41-band low-completeness GeoTIFF.'
        )


        low_task = (
            make_low_completeness_export_task(
                products
            )
        )


        low_task.start()


        print(
            'Started:',
            low_task.id,
        )


# ==============================================================================
# 20. CONFIGURATION SUMMARY
# ==============================================================================

print()

print(
    'Configuration summary'
)

print(
    'EE project:',
    EE_PROJECT,
)

print(
    'Intermediate asset root:',
    INTERMEDIATE_ASSET_ROOT,
)

print(
    'Final destination:',
    EXPORT_DESTINATION,
)

print(
    'Output CRS:',
    OUTPUT_CRS,
)

print(
    'Output transform:',
    OUTPUT_TRANSFORM,
)

print(
    'Final band order:',
    FINAL_BANDS,
)

print(
    'Completeness threshold:',
    COMPLETENESS_THRESHOLD,
)

print(
    'Secondary fallback year for 1979-1986:',
    SECONDARY_FALLBACK_YEAR,
)

print(
    'Logging fallback year for 1979-1987:',
    LOGGING_FALLBACK_YEAR,
)

print(
    '1979-1984 LULC/edge/fire proxy year:',
    START_YEAR,
)

print(
    '1979-1984 secondary proxy year:',
    SECONDARY_FALLBACK_YEAR,
)

print(
    '1979-1984 logging proxy year:',
    LOGGING_FALLBACK_YEAR,
)

print(
    'Sum tolerance:',
    SUM_TOLERANCE,
)
