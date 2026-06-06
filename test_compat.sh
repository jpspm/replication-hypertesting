#!/bin/bash
cd /hypertesting

test_sample() {
    local sampledir="$1"
    local name=$(basename "$sampledir")

    local method=$(head -1 "$sampledir/method.txt")
    local modifier=$(sed -n '2p' "$sampledir/method.txt")
    local javafile=$(ls "$sampledir/program/"*.java 2>/dev/null | head -1)

    if [ -z "$javafile" ]; then
        echo "FAIL $name: no java file"
        return
    fi

    local static_flag=""
    [ "$modifier" = "static" ] && static_flag="--static"

    rm -f /tmp/test-report.json /tmp/test-log.log

    java -DlogFilename=/tmp/test-log -jar bin/hypercoveragetester.jar \
      -c="$javafile" \
      -m="$method" $static_flag \
      -s="$sampledir/settings.conf" \
      -r=/tmp/test-report.json -p=20 -z=10 2>/dev/null

    if [ -f /tmp/test-report.json ]; then
        echo "PASS $name"
    else
        local err=$(grep -i "error\|exception\|fail" /tmp/test-log.log 2>/dev/null | head -1 | cut -c1-100)
        echo "FAIL $name: $err"
    fi
}

for sample in /hypertesting/datasets/NewDataset/*/; do
    test_sample "$sample"
done
