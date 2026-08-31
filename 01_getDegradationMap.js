// ============================================================================
// MAPBIOMAS BRAZIL COLLECTION 10.1
//
// Integrated annual classification:
//
//   1 = TTF   Floresta Intacta
//   2 = TTFd  Floresta Degradada
//   3 = TTS   Vegetacao Secundaria
//   4 = TTCe  Cerrado / Savana
//   5 = TTP   Pastagem
//   6 = TTA   Agricultura
//   7 = TTW   Agua
//   8 = OTH   Outros
//
// PERIOD:
//   1985-2019
//
// PRECEDENCE:
//   TTS > TTFd > TTF
//
// DEGRADATION:
//   edge <= 150 m
//   OR fire == 1
//   OR logging == 1
//
// IMPORTANT:
// Logging only covers Legal Amazon.
// Outside its footprint logging is explicitly treated as ZERO contribution,
// NOT as masked / NoData.
//
// This prevents the logging footprint from restricting edge/fire.
// ============================================================================


// ============================================================================
// 1. INPUT ASSETS
// ============================================================================

var ASSET_LULC =
  'projects/mapbiomas-public/assets/brazil/lulc/collection10_1/' +
  'mapbiomas_brazil_collection10_1_coverage_v1';


var ASSET_SECONDARY =
  'projects/mapbiomas-public/assets/brazil/lulc/collection10_1/' +
  'mapbiomas_brazil_collection10_1_deforestation_secondary_vegetation_v3';


var ASSET_EDGE =
  'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/public/' +
  'degradation_edge_area_col101_v2';


var ASSET_FIRE =
  'projects/mapbiomas-public/assets/brazil/fire/collection5/' +
  'mapbiomas_fire_collection5_annual_burned_v1';


var ASSET_LOGGING =
  'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/public/' +
  'logging_v2';


// Load images.

var lulc =
  ee.Image(ASSET_LULC);

var secondary =
  ee.Image(ASSET_SECONDARY);

var edge =
  ee.Image(ASSET_EDGE);

var fire =
  ee.Image(ASSET_FIRE);

var logging =
  ee.Image(ASSET_LOGGING);


// ============================================================================
// 2. TEMPORAL SETTINGS
// ============================================================================

var START_YEAR = 1985;

var END_YEAR = 2019;


// Secondary vegetation product starts in 1987.
var SECONDARY_START_YEAR = 1987;


// Logging starts in 1988.
var LOGGING_START_YEAR = 1988;


// Edge threshold in meters.
var EDGE_THRESHOLD_M = 150;


// QC threshold:
// flag years where secondary + degradation overlap exceeds 2%
// of forest-base pixels.
var QC_WARNING_THRESHOLD = 0.02;


// ============================================================================
// 3. OUTPUT CODES
// ============================================================================

var OUT = {

  // Floresta intacta
  TTF: 1,

  // Floresta degradada
  TTFd: 2,

  // Vegetacao secundaria
  TTS: 3,

  // Cerrado / Savana
  TTCe: 4,

  // Pastagem
  TTP: 5,

  // Agricultura
  TTA: 6,

  // Agua
  TTW: 7,

  // Outros
  OTH: 8
};


// ============================================================================
// 4. MAPBIOMAS BASE CLASS DEFINITIONS
// ============================================================================


// ---------------------------------------------------------------------------
// Forest base
//
// These pixels are eligible to become:
//
// TTF
// TTFd
//
// Secondary vegetation can override them to TTS.
// ---------------------------------------------------------------------------

var CODES_FOREST = [

  3,   // Formacao Florestal

  5,   // Mangue

  6,   // Floresta Alagavel

  49   // Restinga Arborea
];


// ---------------------------------------------------------------------------
// Cerrado / Savanna
// ---------------------------------------------------------------------------

var CODES_TTCE = [

  4    // Formacao Savanica
];


// ---------------------------------------------------------------------------
// Pasture
//
// Official C10 pasture class.
// ---------------------------------------------------------------------------

var CODES_TTP = [

  15   // Pastagem
];


// ---------------------------------------------------------------------------
// Agriculture
// ---------------------------------------------------------------------------

var CODES_TTA = [

  9,   // Silvicultura

  18,  // Agricultura

  19,  // Lavoura Temporaria

  20,  // Cana-de-acucar

  39,  // Soja

  40,  // Arroz

  41,  // Outras Lavouras Temporarias

  62,  // Algodao

  36,  // Lavoura Perene

  46,  // Cafe

  47,  // Citrus

  35,  // Dende

  48   // Outras Lavouras Perenes
];


// ---------------------------------------------------------------------------
// Water
// ---------------------------------------------------------------------------

var CODES_TTW = [

  31,  // Aquicultura

  33   // Rio, Lago e Oceano
];


// ---------------------------------------------------------------------------
// Secondary vegetation product
//
// You requested values:
//   3
//   5
// ---------------------------------------------------------------------------

var CODES_SECONDARY = [

  3,

  5
];


// ============================================================================
// 5. HELPER FUNCTIONS
// ============================================================================


// ---------------------------------------------------------------------------
// Test whether an image belongs to a list of classes.
//
// Returns:
//
// 1 = class is in list
// 0 = otherwise
//
// Mask is preserved here; caller can unmask afterward.
// ---------------------------------------------------------------------------

function isInCodes(image, codes) {

  var ones = codes.map(function(code) {
    return 1;
  });


  return image
    .remap(
      codes,
      ones,
      0
    )
    .eq(1);
}


// ---------------------------------------------------------------------------
// Create an explicit zero raster using the reference image.
//
// IMPORTANT:
//
// unmask(0, false)
//
// false = allow the replacement image footprint to extend beyond the
// original footprint.
//
// We subsequently constrain the raster using validData.
// ---------------------------------------------------------------------------

function zeroLike(reference) {

  return reference
    .multiply(0)
    .unmask(0, false)
    .toByte();
}


// ============================================================================
// 6. BASE RECLASSIFICATION
// ============================================================================

function reclassifyBase(lulcYear) {


  // Everything begins as OTH.
  //
  // This keeps any remaining MapBiomas code automatically classified
  // as OTH.

  var output = lulcYear
    .multiply(0)
    .add(OUT.OTH)
    .toByte();


  // ------------------------------------------------------------------------
  // Forest -> TTF initially
  // ------------------------------------------------------------------------

  output = output.where(

    isInCodes(
      lulcYear,
      CODES_FOREST
    ),

    OUT.TTF
  );


  // ------------------------------------------------------------------------
  // Cerrado / Savanna
  // ------------------------------------------------------------------------

  output = output.where(

    isInCodes(
      lulcYear,
      CODES_TTCE
    ),

    OUT.TTCe
  );


  // ------------------------------------------------------------------------
  // Pasture
  // ------------------------------------------------------------------------

  output = output.where(

    isInCodes(
      lulcYear,
      CODES_TTP
    ),

    OUT.TTP
  );


  // ------------------------------------------------------------------------
  // Agriculture
  // ------------------------------------------------------------------------

  output = output.where(

    isInCodes(
      lulcYear,
      CODES_TTA
    ),

    OUT.TTA
  );


  // ------------------------------------------------------------------------
  // Water
  // ------------------------------------------------------------------------

  output = output.where(

    isInCodes(
      lulcYear,
      CODES_TTW
    ),

    OUT.TTW
  );


  return output.toByte();
}


// ============================================================================
// 7. PROCESS ONE YEAR
// ============================================================================

function buildYear(year) {


  // year is a client-side number because we call this function
  // from a standard JavaScript for-loop.

  year = Number(year);


  // ========================================================================
  // STEP 0
  // MAPBIOMAS LULC
  // ========================================================================

  var lulcYear = lulc
    .select(
      'classification_' + year
    )
    .rename(
      'lulc_' + year
    );


  // ========================================================================
  // VALID MAPBIOMAS DOMAIN
  //
  // Build an explicit 0/1 raster:
  //
  // 1 = valid MapBiomas coverage
  // 0 = outside coverage
  //
  // The important point is that this image itself is unmasked.
  // ========================================================================

  var validData = lulcYear
    .mask()
    .gt(0)
    .unmask(0, false)
    .rename(
      'valid_data_' + year
    );


  // ========================================================================
  // STEP 1
  // BASE FOREST MASK
  //
  // Forest = 3,5,6,49
  // ========================================================================

  var forestBase = isInCodes(
      lulcYear,
      CODES_FOREST
    )

    // Make explicitly 0 outside the LULC footprint.
    .unmask(0, false)

    // Restrict to valid MapBiomas data.
    .and(validData)

    .rename(
      'forest_base_' + year
    )

    .toByte();


  // ========================================================================
  // STEP 2
  // BASE RECLASSIFICATION
  // ========================================================================

  var base = reclassifyBase(
      lulcYear
    )
    .rename(
      'base_' + year
    );


  // ========================================================================
  // STEP 3
  // SECONDARY VEGETATION
  //
  // PRECEDENCE RULE #1
  //
  // If secondary vegetation is true:
  //
  //       final = TTS
  //
  // independent of contemporaneous LULC base code.
  // ========================================================================

  var secondaryRaw;


  if (year >= SECONDARY_START_YEAR) {


    var secondaryYear = secondary
      .select(
        'classification_' + year
      );


    secondaryRaw = isInCodes(
        secondaryYear,
        CODES_SECONDARY
      )

      // CRITICAL:
      // Turn masked / outside footprint into zero.
      .unmask(0, false)

      // Restrict analysis to Brazil MapBiomas domain.
      .and(validData);


  } else {


    // 1985-1986:
    // no secondary vegetation product.

    secondaryRaw = zeroLike(
        lulcYear
      )
      .and(validData);

  }


  secondaryRaw = secondaryRaw
    .rename(
      'secondary_' + year
    )
    .toByte();


  // ========================================================================
  // STEP 4
  // EDGE DEGRADATION
  //
  // edge_YEAR <= 150
  // ========================================================================

  var edgeDistance = edge
    .select(
      'edge_' + year
    )
    .rename(
      'edge_distance_' + year
    );


  // IMPORTANT:
  //
  // Threshold BEFORE unmask.
  //
  // This prevents NoData from being interpreted as distance = 0.
  //
  // Only pixels that actually satisfy <=150 become 1.
  // Missing pixels become zero afterward.

  var edgeRaw = edgeDistance

    .lte(
      EDGE_THRESHOLD_M
    )

    // Explicit 0 outside source footprint / masks.
    .unmask(0, false)

    // Brazil only.
    .and(validData)

    .rename(
      'edge_raw_' + year
    )

    .toByte();


  // Edge eligible to generate TTFd.

  var edgeForest = edgeRaw
    .and(forestBase)
    .rename(
      'edge_forest_' + year
    )
    .toByte();


  // ========================================================================
  // STEP 5
  // FIRE DEGRADATION
  //
  // burned_area_YEAR == 1
  // ========================================================================

  var fireRaw = fire

    .select(
      'burned_area_' + year
    )

    .eq(1)

    // Missing / outside fire footprint contributes ZERO.
    .unmask(0, false)

    .and(validData)

    .rename(
      'fire_raw_' + year
    )

    .toByte();


  var fireForest = fireRaw
    .and(forestBase)
    .rename(
      'fire_forest_' + year
    )
    .toByte();


  // ========================================================================
  // STEP 6
  // LOGGING
  //
  // logging_YEAR == 1
  //
  // Logging exists only over Legal Amazon.
  //
  // VERY IMPORTANT:
  //
  // Outside its geographic footprint:
  //
  //     logging contribution = 0
  //
  // NOT:
  //
  //     masked / NoData
  //
  // This is what prevents logging from truncating edge/fire.
  // ========================================================================

  var loggingRaw;


  if (year >= LOGGING_START_YEAR) {


    loggingRaw = logging

      .select(
        'logging_' + year
      )

      .eq(1)

      // ================================================================
      // CRITICAL FIX
      // ================================================================
      //
      // sameFootprint = false
      //
      // Thus areas outside Legal Amazon become explicit zero rather
      // than retaining the logging footprint/mask.
      //
      // ================================================================

      .unmask(0, false)

      // Restrict back to valid Brazil coverage.
      .and(validData);


  } else {


    // 1985-1987:
    // no logging product.

    loggingRaw = zeroLike(
        lulcYear
      )
      .and(validData);

  }


  loggingRaw = loggingRaw
    .rename(
      'logging_raw_' + year
    )
    .toByte();


  var loggingForest = loggingRaw
    .and(forestBase)
    .rename(
      'logging_forest_' + year
    )
    .toByte();


  // ========================================================================
  // STEP 7
  // COMBINE RAW DEGRADATION DRIVERS
  //
  // Important architecture:
  //
  // FIRST:
  //
  //     edge OR fire OR logging
  //
  // THEN:
  //
  //     restrict to forestBase
  //
  //
  // Every driver is explicitly 0/1 and unmasked.
  //
  // Therefore a geographically restricted driver cannot mask
  // another driver.
  // ========================================================================

  var degradationRaw = edgeRaw

    // Defensive normalization.
    .unmask(0, false)

    .or(

      fireRaw
        .unmask(0, false)

    )

    .or(

      loggingRaw
        .unmask(0, false)

    )

    .and(validData)

    .rename(
      'degradation_raw_' + year
    )

    .toByte();


  // ========================================================================
  // STEP 8
  // FOREST-ELIGIBLE DEGRADATION
  //
  // Only MapBiomas classes:
  //
  // 3, 5, 6, 49
  //
  // can become TTFd.
  // ========================================================================

  var degradationForest = degradationRaw

    .and(forestBase)

    .rename(
      'degradation_forest_' + year
    )

    .toByte();


  // ========================================================================
  // STEP 9
  // QC OVERLAP
  //
  // Secondary AND degradation occurring simultaneously.
  //
  // For the requested rule-1-vs-rule-2 conflict statistics,
  // count only cases where rule 2 would otherwise be eligible:
  //
  // secondary
  // AND degradation
  // AND forestBase
  //
  // ========================================================================

  var secondaryDegradationOverlap = secondaryRaw

    .and(degradationRaw)

    .and(forestBase)

    .rename(
      'secondary_degradation_overlap_' + year
    )

    .toByte();


  // ========================================================================
  // STEP 10
  // EXPLICIT ONE-HOT FOREST STATES
  // ========================================================================


  // ------------------------------------------------------------------------
  // TTS
  //
  // Highest precedence.
  //
  // New protocol explicitly states:
  //
  // secondary -> TTS
  //
  // independently of contemporaneous base code.
  // ------------------------------------------------------------------------

  var ttsMask = secondaryRaw

    .rename(
      'TTS_mask_' + year
    )

    .toByte();


  // ------------------------------------------------------------------------
  // TTFd
  //
  // Forest
  // AND degradation
  // AND NOT secondary
  // ------------------------------------------------------------------------

  var ttfdMask = forestBase

    .and(degradationRaw)

    .and(
      ttsMask.not()
    )

    .rename(
      'TTFd_mask_' + year
    )

    .toByte();


  // ------------------------------------------------------------------------
  // TTF
  //
  // Forest
  // AND NOT degradation
  // AND NOT secondary
  // ------------------------------------------------------------------------

  var ttfMask = forestBase

    .and(
      degradationRaw.not()
    )

    .and(
      ttsMask.not()
    )

    .rename(
      'TTF_mask_' + year
    )

    .toByte();


  // ========================================================================
  // STEP 11
  // FINAL CLASSIFICATION
  //
  // Start with base categories.
  //
  // Then:
  //
  // TTFd overwrite
  // TTS overwrite LAST
  //
  // TTS therefore always wins.
  // ========================================================================

  var final = base;


  // Rule #2.
  final = final.where(
    ttfdMask,
    OUT.TTFd
  );


  // Rule #1.
  //
  // Deliberately applied LAST.
  final = final.where(
    ttsMask,
    OUT.TTS
  );


  final = final

    .rename(
      'classification_' + year
    )

    .toByte()

    .set({

      year: year,

      precedence:
        'TTS > TTFd > TTF',

      edge_threshold_m:
        EDGE_THRESHOLD_M,

      logging_coverage:
        'Legal Amazon; zero contribution outside source footprint'
    });


  // ========================================================================
  // STEP 12
  // ONE-HOT PARTITION QC
  //
  // Because TTS may occur outside forestBase according to the protocol,
  // the classification domain is:
  //
  // forestBase OR secondary
  // ========================================================================

  var forestStatusDomain = forestBase
    .or(ttsMask)
    .rename(
      'forest_status_domain_' + year
    );


  var partitionSum = ttfMask

    .add(ttfdMask)

    .add(ttsMask)

    .rename(
      'partition_sum_' + year
    );


  // Error means:
  //
  // domain pixel but TTF+TTFd+TTS != 1

  var partitionError = forestStatusDomain

    .and(
      partitionSum.neq(1)
    )

    .rename(
      'partition_error_' + year
    )

    .toByte();


  // ========================================================================
  // RETURN EVERYTHING FOR DEBUGGING
  // ========================================================================

  return {

    year: year,

    lulc:
      lulcYear,

    validData:
      validData,

    base:
      base,

    forestBase:
      forestBase,

    secondary:
      secondaryRaw,

    edgeDistance:
      edgeDistance,

    edgeRaw:
      edgeRaw,

    edgeForest:
      edgeForest,

    fireRaw:
      fireRaw,

    fireForest:
      fireForest,

    loggingRaw:
      loggingRaw,

    loggingForest:
      loggingForest,

    degradationRaw:
      degradationRaw,

    degradation:
      degradationForest,

    overlap:
      secondaryDegradationOverlap,

    ttfMask:
      ttfMask,

    ttfdMask:
      ttfdMask,

    ttsMask:
      ttsMask,

    partitionSum:
      partitionSum,

    partitionError:
      partitionError,

    final:
      final
  };
}


// ============================================================================
// 8. QC REGION
// ============================================================================

// MapBiomas Brazil footprint.
//
// We export / calculate only in the LULC domain.

var QC_REGION = lulc
  .select(
    'classification_' + START_YEAR
  )
  .geometry();


// ============================================================================
// 9. CREATE ANNUAL QC RECORD
// ============================================================================

function makeQAFeature(result) {


  var year =
    result.year;


  // ========================================================================
  // Binary images -> pixel counts.
  //
  // Each image is 0/1.
  // Sum therefore gives number of pixels.
  // ========================================================================

  var qaImage = ee.Image.cat([


    result.forestBase
      .rename(
        'forest_base_pixels'
      ),


    result.secondary
      .rename(
        'secondary_pixels'
      ),


    result.edgeForest
      .rename(
        'edge_forest_pixels'
      ),


    result.fireForest
      .rename(
        'fire_forest_pixels'
      ),


    result.loggingForest
      .rename(
        'logging_forest_pixels'
      ),


    result.degradation
      .rename(
        'degradation_forest_pixels'
      ),


    result.overlap
      .rename(
        'secondary_degradation_overlap_pixels'
      ),


    result.ttfMask
      .rename(
        'TTF_pixels'
      ),


    result.ttfdMask
      .rename(
        'TTFd_pixels'
      ),


    result.ttsMask
      .rename(
        'TTS_pixels'
      ),


    result.partitionError
      .rename(
        'partition_error_pixels'
      )

  ])

  // Defensive:
  // no missing values during QA.
  .unmask(0, false)

  .toByte();


  var stats = qaImage.reduceRegion({

    reducer:
      ee.Reducer.sum(),

    geometry:
      QC_REGION,

    scale:
      30,

    maxPixels:
      1e13,

    tileScale:
      4
  });


  // ========================================================================
  // FOREST DENOMINATOR
  //
  // The requested overlap fraction denominator:
  //
  // all base-forest pixels (3,5,6,49)
  // ========================================================================

  var forestPixels = ee.Number(

    stats.get(
      'forest_base_pixels'
    )

  );


  var overlapPixels = ee.Number(

    stats.get(
      'secondary_degradation_overlap_pixels'
    )

  );


  // ========================================================================
  // OVERLAP FRACTION
  // ========================================================================

  var overlapFraction = ee.Number(

    ee.Algorithms.If(

      forestPixels.gt(0),

      overlapPixels
        .divide(
          forestPixels
        ),

      0

    )
  );


  var overlapPercent = overlapFraction
    .multiply(100);


  // ========================================================================
  // RETURN QA FEATURE
  // ========================================================================

  return ee.Feature(
    null,
    {

      year:
        year,


      forest_base_pixels:
        forestPixels,


      secondary_pixels:
        stats.get(
          'secondary_pixels'
        ),


      edge_forest_pixels:
        stats.get(
          'edge_forest_pixels'
        ),


      fire_forest_pixels:
        stats.get(
          'fire_forest_pixels'
        ),


      logging_forest_pixels:
        stats.get(
          'logging_forest_pixels'
        ),


      degradation_forest_pixels:
        stats.get(
          'degradation_forest_pixels'
        ),


      secondary_degradation_overlap_pixels:
        overlapPixels,


      overlap_fraction_of_forest:
        overlapFraction,


      overlap_percent_of_forest:
        overlapPercent,


      overlap_gt_2pct:
        overlapFraction.gt(
          0.02
        ),


      overlap_gt_3pct:
        overlapFraction.gt(
          0.03
        ),


      TTF_pixels:
        stats.get(
          'TTF_pixels'
        ),


      TTFd_pixels:
        stats.get(
          'TTFd_pixels'
        ),


      TTS_pixels:
        stats.get(
          'TTS_pixels'
        ),


      partition_error_pixels:
        stats.get(
          'partition_error_pixels'
        )
    }
  );
}


// ============================================================================
// 10. BUILD COMPLETE TIME SERIES
// ============================================================================

var annualImages = [];

var qaFeatures = [];


for (
  var year = START_YEAR;
  year <= END_YEAR;
  year++
) {


  var result =
    buildYear(year);


  annualImages.push(
    result.final
  );


  qaFeatures.push(
    makeQAFeature(
      result
    )
  );
}


// ============================================================================
// 11. CREATE MULTIBAND 1985-2019 IMAGE
// ============================================================================

var integratedSeries =
  ee.Image(
    annualImages[0]
  );


for (
  var i = 1;
  i < annualImages.length;
  i++
) {


  integratedSeries =
    integratedSeries.addBands(
      annualImages[i]
    );
}


integratedSeries =
  integratedSeries

    .toByte()

    .set({

      start_year:
        START_YEAR,

      end_year:
        END_YEAR,

      precedence:
        'TTS > TTFd > TTF',

      edge_threshold_m:
        EDGE_THRESHOLD_M,

      output_1:
        'TTF',

      output_2:
        'TTFd',

      output_3:
        'TTS',

      output_4:
        'TTCe',

      output_5:
        'TTP',

      output_6:
        'TTA',

      output_7:
        'TTW',

      output_8:
        'OTH',

      logging_note:
        'Logging source only covers Legal Amazon; outside source footprint contribution is explicitly zero'
    });


// ============================================================================
// 12. QA FEATURE COLLECTION
// ============================================================================

var qaAnnual =
  ee.FeatureCollection(
    qaFeatures
  );


print(
  '========================================================'
);

print(
  'FINAL integrated series',
  integratedSeries
);


print(
  'Final bands',
  integratedSeries.bandNames()
);


print(
  '========================================================'
);

print(
  'Annual QA',
  qaAnnual
);


// ============================================================================
// 13. QC WARNINGS
// ============================================================================


// ---------------------------------------------------------------------------
// >2% overlap
// ---------------------------------------------------------------------------

var warning2pct = qaAnnual.filter(

  ee.Filter.gt(
    'overlap_fraction_of_forest',
    0.02
  )
);


print(
  'WARNING: years with secondary/degradation overlap > 2%',
  warning2pct
);


// ---------------------------------------------------------------------------
// >3% overlap
// ---------------------------------------------------------------------------

var warning3pct = qaAnnual.filter(

  ee.Filter.gt(
    'overlap_fraction_of_forest',
    0.03
  )
);


print(
  'WARNING: years with secondary/degradation overlap > 3%',
  warning3pct
);


// ---------------------------------------------------------------------------
// Partition errors.
//
// EXPECT:
// EMPTY FeatureCollection
// ---------------------------------------------------------------------------

var partitionErrors = qaAnnual.filter(

  ee.Filter.gt(
    'partition_error_pixels',
    0
  )
);


print(
  'PARTITION ERRORS - EXPECT EMPTY',
  partitionErrors
);


// ============================================================================
// 14. QC CHART
//
// Secondary + degradation overlap as fraction of forest-base.
// ============================================================================

var overlapChart =
  ui.Chart.feature.byFeature({

    features:
      qaAnnual,

    xProperty:
      'year',

    yProperties: [
      'overlap_percent_of_forest'
    ]

  })

  .setChartType(
    'LineChart'
  )

  .setOptions({

    title:
      'Secondary vegetation ∩ degradation / forest-base pixels',

    hAxis: {
      title: 'Year'
    },

    vAxis: {
      title: 'Overlap (%)'
    },

    lineWidth:
      2,

    pointSize:
      4
  });


print(
  overlapChart
);


// ============================================================================
// 15. EXAMPLE YEAR
// ============================================================================

// Change this freely.

var EXAMPLE_YEAR = 2019;


var ex =
  buildYear(
    EXAMPLE_YEAR
  );


// ============================================================================
// 16. FINAL PALETTE
// ============================================================================

var OUT_PALETTE = [

  // 1 TTF
  '1b7837',

  // 2 TTFd
  'd95f02',

  // 3 TTS
  '66bd63',

  // 4 TTCe
  'b8e186',

  // 5 TTP
  'e6d96a',

  // 6 TTA
  'c51b7d',

  // 7 TTW
  '2166ac',

  // 8 OTH
  'bdbdbd'
];


// ============================================================================
// 17. MAP
// ============================================================================

Map.setCenter(
  -53,
  -14,
  4
);


// ============================================================================
// 17.1 ORIGINAL LULC
// ============================================================================

Map.addLayer(

  ex.lulc
    .randomVisualizer(),

  {},

  '00 - Original C10.1 ' +
    EXAMPLE_YEAR,

  false
);


// ============================================================================
// 17.2 BASE RECLASSIFICATION
// ============================================================================

Map.addLayer(

  ex.base,

  {
    min:
      1,

    max:
      8,

    palette:
      OUT_PALETTE
  },

  '01 - Base reclassification',

  false
);


// ============================================================================
// 17.3 FOREST BASE
// ============================================================================

Map.addLayer(

  ex.forestBase
    .selfMask(),

  {
    palette: [
      '006400'
    ]
  },

  '02 - Forest base 3/5/6/49',

  false
);


// ============================================================================
// 17.4 SECONDARY
// ============================================================================

Map.addLayer(

  ex.secondary
    .selfMask(),

  {
    palette: [
      '00ff00'
    ]
  },

  '03 - Secondary raw - PRIORITY 1',

  false
);


// ============================================================================
// 17.5 EDGE DISTANCE
// ============================================================================

Map.addLayer(

  ex.edgeDistance,

  {
    min:
      0,

    max:
      1000,

    palette: [
      'ff0000',
      'ffff00',
      '00ffff',
      '0000ff'
    ]
  },

  '04a - Edge distance raw',

  false
);


// ============================================================================
// 17.6 EDGE <=150 - RAW
// ============================================================================

Map.addLayer(

  ex.edgeRaw
    .selfMask(),

  {
    palette: [
      'ffff00'
    ]
  },

  '04b - Edge <=150 m RAW',

  false
);


// ============================================================================
// 17.7 EDGE + FOREST
// ============================================================================

Map.addLayer(

  ex.edgeForest
    .selfMask(),

  {
    palette: [
      'ff9900'
    ]
  },

  '04c - Edge <=150 m + forest',

  false
);


// ============================================================================
// 17.8 FIRE RAW
// ============================================================================

Map.addLayer(

  ex.fireRaw
    .selfMask(),

  {
    palette: [
      'ff0000'
    ]
  },

  '05a - Fire RAW',

  false
);


// ============================================================================
// 17.9 FIRE + FOREST
// ============================================================================

Map.addLayer(

  ex.fireForest
    .selfMask(),

  {
    palette: [
      'cc0000'
    ]
  },

  '05b - Fire + forest',

  false
);


// ============================================================================
// 17.10 LOGGING RAW
//
// This should only show positive pixels in Legal Amazon.
//
// IMPORTANT:
// Outside Legal Amazon the raster is ZERO, not masked.
// ============================================================================

Map.addLayer(

  ex.loggingRaw
    .selfMask(),

  {
    palette: [
      'ff00ff'
    ]
  },

  '06a - Logging RAW',

  false
);


// ============================================================================
// 17.11 LOGGING + FOREST
// ============================================================================

Map.addLayer(

  ex.loggingForest
    .selfMask(),

  {
    palette: [
      '800080'
    ]
  },

  '06b - Logging + forest',

  false
);


// ============================================================================
// 17.12 ANY DEGRADATION RAW
//
// This should now work over ALL BRAZIL.
//
// Edge OR fire OR logging.
// ============================================================================

Map.addLayer(

  ex.degradationRaw
    .selfMask(),

  {
    palette: [
      '00ffff'
    ]
  },

  '07a - ANY degradation RAW - Brazil',

  false
);


// ============================================================================
// 17.13 DEGRADATION + FOREST
//
// This is what can become TTFd.
// ============================================================================

Map.addLayer(

  ex.degradation
    .selfMask(),

  {
    palette: [
      'ff6600'
    ]
  },

  '07b - Degradation + forest',

  false
);


// ============================================================================
// 17.14 SECONDARY + DEGRADATION OVERLAP
//
// These pixels are resolved as TTS because TTS has priority.
// ============================================================================

Map.addLayer(

  ex.overlap
    .selfMask(),

  {
    palette: [
      'ff00ff'
    ]
  },

  '08 - Secondary ∩ degradation',

  false
);


// ============================================================================
// 17.15 FINAL TTF
// ============================================================================

Map.addLayer(

  ex.ttfMask
    .selfMask(),

  {
    palette: [
      '1b7837'
    ]
  },

  '09 - TTF final',

  false
);


// ============================================================================
// 17.16 FINAL TTFd
// ============================================================================

Map.addLayer(

  ex.ttfdMask
    .selfMask(),

  {
    palette: [
      'd95f02'
    ]
  },

  '10 - TTFd final',

  false
);


// ============================================================================
// 17.17 FINAL TTS
// ============================================================================

Map.addLayer(

  ex.ttsMask
    .selfMask(),

  {
    palette: [
      '66bd63'
    ]
  },

  '11 - TTS final',

  false
);


// ============================================================================
// 17.18 PARTITION ERRORS
//
// SHOULD BE EMPTY.
// ============================================================================

Map.addLayer(

  ex.partitionError
    .selfMask(),

  {
    palette: [
      'ff0000'
    ]
  },

  '12 - PARTITION ERROR - SHOULD BE EMPTY',

  false
);


// ============================================================================
// 17.19 FINAL INTEGRATED CLASSIFICATION
// ============================================================================

Map.addLayer(

  ex.final,

  {
    min:
      1,

    max:
      8,

    palette:
      OUT_PALETTE
  },

  '13 - FINAL ' +
    EXAMPLE_YEAR,

  true
);


// ============================================================================
// 18. EXAMPLE-YEAR QA
// ============================================================================

print(
  'QA example year ' +
    EXAMPLE_YEAR,

  qaAnnual.filter(

    ee.Filter.eq(
      'year',
      EXAMPLE_YEAR
    )
  )
);


// ============================================================================
// 19. CLICK INSPECTOR
//
// Click any pixel.
//
// This is particularly useful for checking both sides of the former
// Legal Amazon footprint issue.
// ============================================================================

Map.onClick(function(coords) {


  var point = ee.Geometry.Point([

    coords.lon,

    coords.lat
  ]);


  var inspectImage = ee.Image.cat([


    ex.lulc
      .rename(
        'lulc'
      ),


    ex.forestBase
      .rename(
        'forest_base'
      ),


    ex.secondary
      .rename(
        'secondary'
      ),


    ex.edgeDistance
      .rename(
        'edge_distance'
      ),


    ex.edgeRaw
      .rename(
        'edge'
      ),


    ex.fireRaw
      .rename(
        'fire'
      ),


    ex.loggingRaw
      .rename(
        'logging'
      ),


    ex.degradationRaw
      .rename(
        'degradation_raw'
      ),


    ex.degradation
      .rename(
        'degradation_forest'
      ),


    ex.overlap
      .rename(
        'secondary_degradation_overlap'
      ),


    ex.ttfMask
      .rename(
        'TTF'
      ),


    ex.ttfdMask
      .rename(
        'TTFd'
      ),


    ex.ttsMask
      .rename(
        'TTS'
      ),


    ex.final
      .rename(
        'final_class'
      )

  ]);


  var values = inspectImage.reduceRegion({

    reducer:
      ee.Reducer.first(),

    geometry:
      point,

    scale:
      30,

    maxPixels:
      1e6
  });


  print(
    '------------------------------------------------'
  );

  print(
    'Pixel:',
    coords
  );

  print(
    'Values:',
    values
  );

});


// ============================================================================
// 20. LEGEND
// ============================================================================

var legendNames = [

  '1 - TTF  Floresta Intacta',

  '2 - TTFd Floresta Degradada',

  '3 - TTS  Vegetacao Secundaria',

  '4 - TTCe Cerrado/Savana',

  '5 - TTP  Pastagem',

  '6 - TTA  Agricultura',

  '7 - TTW  Agua',

  '8 - OTH  Outros'
];


var legend = ui.Panel({

  style: {

    position:
      'bottom-left',

    padding:
      '8px 12px'
  }
});


legend.add(

  ui.Label({

    value:
      'Integrated classification',

    style: {

      fontWeight:
        'bold',

      fontSize:
        '14px',

      margin:
        '0 0 8px 0'
    }
  })
);


for (
  var k = 0;
  k < legendNames.length;
  k++
) {


  var colorBox = ui.Label({

    style: {

      backgroundColor:
        '#' + OUT_PALETTE[k],

      padding:
        '8px',

      margin:
        '0 6px 4px 0'
    }
  });


  var description = ui.Label({

    value:
      legendNames[k],

    style: {

      margin:
        '0 0 4px 0'
    }
  });


  legend.add(

    ui.Panel({

      widgets: [

        colorBox,

        description
      ],

      layout:

        ui.Panel.Layout.Flow(
          'horizontal'
        )
    })
  );
}


Map.add(
  legend
);


// ============================================================================
// 21. EXPORT SETTINGS
// ============================================================================

// Change to your own project.

var EXPORT_ASSET_ROOT =
  'projects/YOUR_PROJECT/assets/mapbiomas_integrated';


// Set TRUE when ready.

var EXPORT_MULTIBAND = false;

var EXPORT_EACH_YEAR = false;

var EXPORT_QA_CSV = false;


// ============================================================================
// 22. EXPORT MULTIBAND IMAGE
//
// classification_1985
// ...
// classification_2019
// ============================================================================

if (EXPORT_MULTIBAND) {


  Export.image.toAsset({

    image:
      integratedSeries,

    description:
      'mapbiomas_integrated_1985_2019',

    assetId:
      EXPORT_ASSET_ROOT +
      '/mapbiomas_integrated_1985_2019',

    region:
      QC_REGION,

    scale:
      30,

    maxPixels:
      1e13,

    pyramidingPolicy: {

      '.default':
        'mode'
    }
  });
}


// ============================================================================
// 23. EXPORT EACH YEAR SEPARATELY
// ============================================================================

if (EXPORT_EACH_YEAR) {


  for (
    var exportYear = START_YEAR;
    exportYear <= END_YEAR;
    exportYear++
  ) {


    var annual =
      buildYear(
        exportYear
      ).final;


    Export.image.toAsset({

      image:
        annual,

      description:
        'mapbiomas_integrated_' +
        exportYear,

      assetId:
        EXPORT_ASSET_ROOT +
        '/mapbiomas_integrated_' +
        exportYear,

      region:
        QC_REGION,

      scale:
        30,

      maxPixels:
        1e13,

      pyramidingPolicy: {

        '.default':
          'mode'
      }
    });
  }
}


// ============================================================================
// 24. EXPORT QA CSV
// ============================================================================

if (EXPORT_QA_CSV) {


  Export.table.toDrive({

    collection:
      qaAnnual,

    description:
      'QA_mapbiomas_integrated_1985_2019',

    fileNamePrefix:
      'QA_mapbiomas_integrated_1985_2019',

    fileFormat:
      'CSV'
  });
}
