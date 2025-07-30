#! /bin/bash

COVERAGE_FILE=$(pwd)/coverage_thingpress.json
COVERAGE_PERC=$(pwd)/coverage_thingpress_perc

pytest --disable-socket -s \
--cov=$(pwd)/src/bulk_importer \
--cov=$(pwd)/src/certificate_deployer \
--cov=$(pwd)/src/certificate_generator \
--cov=$(pwd)/src/product_verifier \
--cov=$(pwd)/src/provider_espressif \
--cov=$(pwd)/src/provider_generated \
--cov=$(pwd)/src/provider_infineon \
--cov=$(pwd)/src/provider_microchip \
--cov=$(pwd)/src/layer_utils \
--cov-report=json:$COVERAGE_FILE \
test/unit/src

jq -r .totals.percent_covered_display $COVERAGE_FILE > $COVERAGE_PERC
