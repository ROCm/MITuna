from hip import hip
import re

GFX_CHIP_RE = re.compile(r"gfx[0-9a-z]+")
DATA_TYPES_GEMM = ['f32', 'f16', 'bf16', 'i8', 'fp8']
DATA_TYPES_ATTENTION_WMMA = ['i8', 'f16', 'bf16']
DATA_TYPES_ATTENTION_MFMA = ['i8', 'f32', 'f16', 'bf16']

def hip_check(call_result):
    err = call_result[0]
    result = call_result[1:]
    if len(result) == 1:
        result = result[0]
    if isinstance(err, hip.hipError_t) and err != hip.hipError_t.hipSuccess:
        raise RuntimeError(str(err))
    return result

def getArch() -> str:
    agents = set()
    device_count = hip_check(hip.hipGetDeviceCount())
    for device in range(device_count):
        props = hip.hipDeviceProp_t()
        hip_check(hip.hipGetDeviceProperties(props,device))
        agent = props.gcnArchName.decode('utf-8')
        agents.add(agent)
    if(len(agents) > 1):
        print(f"WARNING: Found {len(agents)} different kinds of agents on the same machine :  {', '.join(agents)}")
        print("WARNING: Using the first agent by default. If you want to use a different agent, please set the HIP_VISIBLE_DEVICES environment variable.")
    # select first agent by default
    return list(agents)[0]

def getChip():
    arch = getArch()
    chip = GFX_CHIP_RE.search(arch).group(0)
    return chip

DATA_TYPES_ATTENTION = None

def initializeDataTypesAttention():
    global DATA_TYPES_ATTENTION
    if getChip().startswith('gfx9'):
        DATA_TYPES_ATTENTION = DATA_TYPES_ATTENTION_MFMA
    else:
        DATA_TYPES_ATTENTION = DATA_TYPES_ATTENTION_WMMA
        
    return DATA_TYPES_ATTENTION # For modules that import this function

def matchDtype(config_str):
    return re.search(r"-t\s+(\w+)", config_str)
