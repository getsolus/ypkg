curl https://raw.githubusercontent.com/spdx/license-list-data/refs/heads/main/json/licenses.json |
jq '{enum: [(.licenses[] | select(.isDeprecatedLicenseId == false)).licenseId]}' |
jq '.enum += ["EULA", "Distributable", "Public-Domain"]' > data/schema/licenses.json
