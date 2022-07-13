#!/bin/bash

RED='\e[1;31m' # Red Color
GREEN='\e[1;32m' # Green
NC='\e[0m' # No Color

# Check for valid argument
if [[ -z "$1" ]]; then
	echo -e "${RED}""Provide image path !!!""${NC}"
	echo "USAGE: ./get_region_size.sh <image-path>"
	exit 1
fi

# Check for image path
if [[ ! -e "$1" ]]; then
	echo -e "${RED}""Image does not exist !!!""${NC}"
	exit 1
fi


IMAGE="$1"
FMAP_CMD="dump_fmap -h ${IMAGE}"
CBFS_CMD="cbfstool ${IMAGE} print -r"
VAR_REGION_ARRAY=("FW_MAIN_A" "FW_MAIN_B" "ME_RW_A" "ME_RW_B" "COREBOOT")
FIX_REGION_ARRAY=("RW_LEGACY" "SI_ME" "SI_DESC" "RW_MISC" "RW_FWID_A" "VBLOCK_A" "RW_FWID_B" "VBLOCK_B" "RO_VPD" "FMAP" "RO_FRID" "GBB" "RW_UNUSED_1" "RW_UNUSED_2" "RW_UNUSED_3")

IMAGENAME=$(basename "${IMAGE}")
TEMPOUTFILE="getsizetemp"
OUTFILE="$(echo "${IMAGENAME}" | cut -d '.' -f1)-sizedata.csv"

# Delete output file if already present
if [[ -e ${OUTFILE} ]]; then
	rm -rf "${OUTFILE}"
fi


TOTAL_FMAP_KB=0
TOTAL_CBFS_KB=0
TOTAL_BUFFER_KB=0

region_fmap_size()
{
	DATA_STR=$(${FMAP_CMD} | grep "$1" | tr -s ' ')
	echo "${DATA_STR}" | cut -d ' ' -f5
}

calculate_region_total_size()
{
	REGION_TOTAL_SIZE=0

	REGION_TOTAL_SIZE=$(${CBFS_CMD} "$1" | tr -s ' ' | { while read -r CURRENT_LINE; do
		FILE_NAME=$(echo "${CURRENT_LINE}" | cut -d " " -f1)
		FILE_SIZE=$(echo "${CURRENT_LINE}" | cut -d " " -f4)
		if [[ ${FILE_NAME} == 'Name' || ${FILE_NAME} == 'FMAP' || ${FILE_NAME} == '(empty)' ]]; then
			continue
		fi
		if [[ ! ${FILE_SIZE} =~ [0-9] ]]; then
			FILE_SIZE=$(echo "${CURRENT_LINE}" | cut -d " " -f5)
		fi
		REGION_TOTAL_SIZE=$((REGION_TOTAL_SIZE + FILE_SIZE))
	done
	echo "${REGION_TOTAL_SIZE}"
	})

	echo "${REGION_TOTAL_SIZE}"
}

var_region_data_final()
{
	REGION_FMAP_SIZE=$(region_fmap_size "$1")
	REGION_FMAP_SIZE_INT=$((16#"${REGION_FMAP_SIZE}"))
	REGION_CBFS_SIZE=$(calculate_region_total_size "$1")
	BUFFER=$((REGION_FMAP_SIZE_INT - REGION_CBFS_SIZE))
	echo "$1"' '"$((REGION_FMAP_SIZE_INT / 1024))"' '"$((REGION_CBFS_SIZE / 1024))"' '"$((BUFFER / 1024))"
}

fix_region_data_final()
{
	REGION_FMAP_SIZE=$(region_fmap_size "$1")
	REGION_FMAP_SIZE_INT=$((16#"${REGION_FMAP_SIZE}"))
	REGION_FMAP_SIZE_INT_KB=$((REGION_FMAP_SIZE_INT / 1024))
	if [[ ${REGION_FMAP_SIZE_INT_KB} != 0 ]]; then
		echo "$1"' '"${REGION_FMAP_SIZE_INT_KB}"' '"${REGION_FMAP_SIZE_INT_KB}"' '"0"
	fi
}

output_fun()
{
	echo "NAME FMAP_SIZE(KB) CBFS_SIZE(KB) BUFFER(KB)"
	for vreg in "${VAR_REGION_ARRAY[@]}"
	do
		var_region_data_final "${vreg}"
	done

	for freg in "${FIX_REGION_ARRAY[@]}"
	do
		${FMAP_CMD} | grep "${freg}" > /dev/null 2>&1 && fix_region_data_final "${freg}"
	done
}

echo -e "Fetching size data from ${RED}${IMAGENAME}${NC} and generating ${RED}${OUTFILE}${NC}..."
output_fun >> "${TEMPOUTFILE}"

while read -r CURRENT_LINE; do
	NAME=$(echo "${CURRENT_LINE}" | cut -d ' ' -f1)
	FMAP_KB=$(echo "${CURRENT_LINE}" | cut -d ' ' -f2)
	CBFS_KB=$(echo "${CURRENT_LINE}" | cut -d ' ' -f3)
	BUFFER_KB=$(echo "${CURRENT_LINE}" | cut -d ' ' -f4)
	if [[ ${NAME} != "NAME" ]]; then
		TOTAL_FMAP_KB=$((TOTAL_FMAP_KB + FMAP_KB))
		TOTAL_CBFS_KB=$((TOTAL_CBFS_KB + CBFS_KB))
		TOTAL_BUFFER_KB=$((TOTAL_BUFFER_KB + BUFFER_KB))
	fi
	printf "%-15s %-15s %-15s %-15s\n" "${NAME}" "${FMAP_KB}" "${CBFS_KB}" "${BUFFER_KB}"
	echo "${NAME},${FMAP_KB},${CBFS_KB},${BUFFER_KB}" >> "${OUTFILE}"
done < "${TEMPOUTFILE}"

printf "%-15s %-15s %-15s %-15s\n" "Total" "${TOTAL_FMAP_KB}" "${TOTAL_CBFS_KB}" "${TOTAL_BUFFER_KB}"
echo "TOTAL,${TOTAL_FMAP_KB},${TOTAL_CBFS_KB},${TOTAL_BUFFER_KB}" >> "${OUTFILE}"
rm -rf "${TEMPOUTFILE}"
echo -e "${GREEN}""${OUTFILE} is ready ...""${NC}"
