set(DBMERGE_SRC pdbmerge.cpp)

add_executable(pdbmerge ${DBMERGE_SRC})

target_include_directories(pdbmerge PUBLIC $<BUILD_INTERFACE:${Boost_INCLUDE_DIRS}>)

clang_tidy_check(pdbmerge)

target_internal_library(pdbmerge
    optimized ${Boost_FILESYSTEM_LIBRARY_RELEASE}
    optimized ${Boost_SYSTEM_LIBRARY_RELEASE}
    debug ${Boost_FILESYSTEM_LIBRARY_DEBUG}
    debug ${Boost_SYSTEM_LIBRARY_DEBUG}
)
