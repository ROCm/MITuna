#!/usr/bin/env bash
###############################################################################
#
# MIT License
#
# Copyright (c) 2022 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
ROCMINFO=$(which rocminfo)
if [ -z "$ROCMINFO" ];
then
    ROCMINFO=/opt/rocm/bin/rocminfo;
fi

if [ ! -f $ROCMINFO ];
then
    echo "rocminfo is not installed, please install the rocminfo package"
    return -1
fi
arches=$($ROCMINFO | grep -e ' gfx' -e 'Compute Unit:' | awk '/Name/{ arch= $2} /Compute Unit:/ {if(arch != "") { all_arches[(arch "-" $3)]++ }} END { for (a in all_arches) { print a "-" all_arches[a]}  }')

while IFS= read -r line ; 
do 
    echo $line
done <<< "$arches"
