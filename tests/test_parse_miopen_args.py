#!/usr/bin/env python3
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
"""
Tests for MIOpen argument parsing module.

This module tests all parser functions in tuna/miopen/parse_miopen_args.py,
including argument validation, default values, and error handling.
"""

import pytest

from tuna.miopen.parse_miopen_args import (get_import_cfg_parser,
                                           get_load_job_parser,
                                           get_export_db_parser,
                                           get_update_golden_parser)
from tuna.miopen.db.benchmark import FrameworkEnum, ModelEnum
from tuna.miopen.utils.config_type import ConfigType

# ============================================================================
# Tests for get_import_cfg_parser
# ============================================================================


@pytest.mark.unit
@pytest.mark.miopen
class TestImportConfigParser:
  """Tests for import_configs subcommand parser."""

  def test_parser_creation(self):
    """Test that parser can be created successfully."""
    parser = get_import_cfg_parser()
    assert parser is not None

  def test_parser_with_yaml(self):
    """Test parser creation with YAML support."""
    parser = get_import_cfg_parser(with_yaml=True)
    assert parser is not None

  def test_parser_without_yaml(self):
    """Test parser creation without YAML support."""
    parser = get_import_cfg_parser(with_yaml=False)
    assert parser is not None

  def test_version_argument(self):
    """Test --version argument parsing."""
    parser = get_import_cfg_parser()
    # Note: VERSION argument doesn't have a short flag in jsonargparse
    # Just test that parser can be created - version is handled by TunaArgs
    assert parser is not None

  def test_config_type_argument(self):
    """Test --config_type argument parsing."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-C', 'convolution'])
    assert args.config_type == ConfigType.convolution

  def test_file_name_argument(self):
    """Test --file_name argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-f', 'test_file.txt'])
    assert args.file_name == 'test_file.txt'

  def test_tag_argument(self):
    """Test --tag argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-t', 'test_tag'])
    assert args.tag == 'test_tag'

  def test_tag_only_argument(self):
    """Test --tag_only flag."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-T'])
    assert args.tag_only is True

  def test_mark_recurrent_argument(self):
    """Test --mark_recurrent flag."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--mark_recurrent'])
    assert args.mark_recurrent is True

  def test_batches_argument(self):
    """Test --batches argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-b', '64,128,256'])
    assert args.batches == '64,128,256'

  def test_command_argument_valid_choices(self):
    """Test --command argument with valid choices."""
    parser = get_import_cfg_parser()
    for cmd in ['conv', 'convfp16', 'convbfp16']:
      args = parser.parse_args(['-c', cmd])
      assert args.command == cmd

  def test_command_argument_invalid_choice(self):
    """Test --command argument with invalid choice."""
    parser = get_import_cfg_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(['-c', 'invalid_cmd'])

  @pytest.mark.parametrize("framework", [frm.value for frm in FrameworkEnum])
  def test_framework_choices(self, framework):
    """Test that all framework enum values are valid choices."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-F', framework])
    assert args.framework == framework

  @pytest.mark.parametrize("model", [model.value for model in ModelEnum])
  def test_model_choices(self, model):
    """Test that all model enum values are valid choices."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-m', model])
    assert args.model == model

  def test_add_framework_argument(self):
    """Test --add_framework mutually exclusive option."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--add_framework', 'Pytorch'])
    assert args.add_framework == 'Pytorch'

  def test_add_model_argument(self):
    """Test --add_model mutually exclusive option."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--add_model', 'Resnet50'])
    assert args.add_model == 'Resnet50'

  def test_print_models_argument(self):
    """Test --print_models mutually exclusive option."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--print_models'])
    assert args.print_models is True

  def test_add_benchmark_argument(self):
    """Test --add_benchmark mutually exclusive option."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--add_benchmark'])
    assert args.add_benchmark is True

  def test_mutually_exclusive_framework_model(self):
    """Test that add_framework and add_model are mutually exclusive."""
    parser = get_import_cfg_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(
          ['--add_framework', 'Pytorch', '--add_model', 'Resnet50'])

  def test_mutually_exclusive_all_options(self):
    """Test mutual exclusivity among all group options."""
    parser = get_import_cfg_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(['--add_framework', 'Pytorch', '--print_models'])

  def test_batchsize_argument(self):
    """Test --batchsize integer argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--batchsize', '256'])
    assert args.batchsize == 256

  def test_driver_argument(self):
    """Test --driver argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-d', './bin/MIOpenDriver'])
    assert args.driver == './bin/MIOpenDriver'

  def test_gpu_count_argument(self):
    """Test --gpu_count integer argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['-g', '8'])
    assert args.gpu_count == 8

  def test_fw_version_argument(self):
    """Test --fw_version integer argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--fw_version', '2'])
    assert args.fw_version == 2

  def test_md_version_argument(self):
    """Test --md_version integer argument."""
    parser = get_import_cfg_parser()
    args = parser.parse_args(['--md_version', '1'])
    assert args.md_version == 1

  def test_default_values(self):
    """Test that default values are set correctly."""
    parser = get_import_cfg_parser()
    args = parser.parse_args([])
    assert args.batchsize is None
    assert args.command is None
    assert args.driver is None
    assert args.gpu_count is None
    assert args.fw_version is None
    assert args.md_version is None


# ============================================================================
# Tests for get_load_job_parser
# ============================================================================


@pytest.mark.unit
@pytest.mark.miopen
class TestLoadJobParser:
  """Tests for load_job subcommand parser."""

  def test_parser_creation(self):
    """Test that parser can be created successfully."""
    parser = get_load_job_parser()
    assert parser is not None

  def test_required_label_argument(self):
    """Test that --label is required."""
    parser = get_load_job_parser()
    with pytest.raises(SystemExit):
      # Missing required --label, --session_id, and config filter
      parser.parse_args([])

  def test_required_session_id_argument(self):
    """Test that --session_id is required."""
    parser = get_load_job_parser()
    with pytest.raises(SystemExit):
      # Missing required --session_id
      parser.parse_args(['-l', 'test_label', '-t', 'test_tag'])

  def test_tag_argument(self):
    """Test --tag config filter."""
    parser = get_load_job_parser()
    args = parser.parse_args(
        ['-t', 'test_tag', '-l', 'test_label', '--session_id', '1'])
    assert args.tag == 'test_tag'
    assert args.label == 'test_label'
    assert args.session_id == 1

  def test_all_configs_argument(self):
    """Test --all_configs config filter."""
    parser = get_load_job_parser()
    args = parser.parse_args(
        ['--all_configs', '-l', 'test', '--session_id', '1'])
    assert args.all_configs is True

  def test_tag_all_configs_mutually_exclusive(self):
    """Test that --tag and --all_configs are mutually exclusive."""
    parser = get_load_job_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(
          ['-t', 'tag', '--all_configs', '-l', 'test', '--session_id', '1'])

  def test_algo_argument(self):
    """Test --algo solver filter."""
    parser = get_load_job_parser()
    args = parser.parse_args([
        '-t', 'tag', '-A', 'miopenConvolutionAlgoDirect', '-l', 'test',
        '--session_id', '1'
    ])
    assert args.algo == 'miopenConvolutionAlgoDirect'

  def test_solvers_argument(self):
    """Test --solvers solver filter."""
    parser = get_load_job_parser()
    args = parser.parse_args([
        '-t', 'tag', '-s', 'ConvAsm1x1U,ConvAsm3x3U', '-l', 'test',
        '--session_id', '1'
    ])
    assert args.solvers == 'ConvAsm1x1U,ConvAsm3x3U'

  def test_algo_solvers_mutually_exclusive(self):
    """Test that --algo and --solvers are mutually exclusive."""
    parser = get_load_job_parser()
    with pytest.raises(SystemExit):
      parser.parse_args([
          '-t', 'tag', '-A', 'miopenConvolutionAlgoDirect', '-s', 'ConvAsm1x1U',
          '-l', 'test', '--session_id', '1'
      ])

  def test_only_dynamic_argument(self):
    """Test --only_dynamic flag."""
    parser = get_load_job_parser()
    args = parser.parse_args(
        ['-t', 'tag', '-d', '-l', 'test', '--session_id', '1'])
    assert args.only_dynamic is True

  def test_tunable_argument(self):
    """Test --tunable flag."""
    parser = get_load_job_parser()
    args = parser.parse_args(
        ['-t', 'tag', '--tunable', '-l', 'test', '--session_id', '1'])
    assert args.tunable is True

  def test_cmd_argument_valid_choices(self):
    """Test --cmd argument with valid choices."""
    parser = get_load_job_parser()
    for cmd in ['conv', 'convfp16', 'convbfp16']:
      args = parser.parse_args(
          ['-t', 'tag', '-c', cmd, '-l', 'test', '--session_id', '1'])
      assert args.cmd == cmd

  def test_cmd_argument_invalid_choice(self):
    """Test --cmd argument with invalid choice."""
    parser = get_load_job_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(
          ['-t', 'tag', '-c', 'invalid', '-l', 'test', '--session_id', '1'])

  def test_fin_steps_argument(self):
    """Test --fin_steps argument with default value."""
    parser = get_load_job_parser()
    args = parser.parse_args(['-t', 'tag', '-l', 'test', '--session_id', '1'])
    assert args.fin_steps == 'not_fin'

    args = parser.parse_args([
        '-t', 'tag', '--fin_steps', 'miopen_find_compile', '-l', 'test',
        '--session_id', '1'
    ])
    assert args.fin_steps == 'miopen_find_compile'

  def test_config_type_argument(self):
    """Test --config_type argument."""
    parser = get_load_job_parser()
    args = parser.parse_args(
        ['-C', 'convolution', '-t', 'tag', '-l', 'test', '--session_id', '1'])
    assert args.config_type == ConfigType.convolution

  def test_version_argument(self):
    """Test --version argument."""
    parser = get_load_job_parser()
    # Note: VERSION argument doesn't have a short flag in jsonargparse
    # Just test that parser can be created - version is handled by TunaArgs
    assert parser is not None

  def test_complete_args_set(self):
    """Test parsing complete argument set."""
    parser = get_load_job_parser()
    args = parser.parse_args([
        '-t', 'test_tag', '-l', 'test_label', '--session_id', '123', '-A',
        'miopenConvolutionAlgoDirect', '-d', '--tunable', '-c', 'convfp16',
        '--fin_steps', 'miopen_find_compile', '-C', 'convolution'
    ])
    assert args.tag == 'test_tag'
    assert args.label == 'test_label'
    assert args.session_id == 123
    assert args.algo == 'miopenConvolutionAlgoDirect'
    assert args.only_dynamic is True
    assert args.tunable is True
    assert args.cmd == 'convfp16'
    assert args.fin_steps == 'miopen_find_compile'
    assert args.config_type == ConfigType.convolution


# ============================================================================
# Tests for get_export_db_parser
# ============================================================================


@pytest.mark.unit
@pytest.mark.miopen
class TestExportDbParser:
  """Tests for export_db subcommand parser."""

  def test_parser_creation(self):
    """Test that parser can be created successfully."""
    parser = get_export_db_parser()
    assert parser is not None

  def test_session_id_argument(self):
    """Test --session_id mutually exclusive option."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f'])
    assert args.session_id == 1

  def test_golden_v_argument(self):
    """Test --golden_v mutually exclusive option."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--golden_v', '220', '-a', 'gfx90a', '-n', '110', '-f'])
    assert args.golden_v == 220

  def test_session_golden_mutually_exclusive(self):
    """Test that --session_id and --golden_v are mutually exclusive."""
    parser = get_export_db_parser()
    with pytest.raises(SystemExit):
      parser.parse_args([
          '--session_id', '1', '--golden_v', '220', '-a', 'gfx90a', '-n', '110',
          '-f'
      ])

  def test_missing_version_argument(self):
    """Test that one of session_id or golden_v is required."""
    parser = get_export_db_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(['-a', 'gfx90a', '-n', '110', '-f'])

  def test_find_db_argument(self):
    """Test --find_db database type option."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f'])
    assert args.find_db is True

  def test_kern_db_argument(self):
    """Test --kern_db database type option."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-k'])
    assert args.kern_db is True

  def test_perf_db_argument(self):
    """Test --perf_db database type option."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-p'])
    assert args.perf_db is True

  def test_db_type_mutually_exclusive(self):
    """Test that database type options are mutually exclusive."""
    parser = get_export_db_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(
          ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f', '-k'])

  def test_missing_db_type(self):
    """Test that one database type is required."""
    parser = get_export_db_parser()
    with pytest.raises(SystemExit):
      parser.parse_args(['--session_id', '1', '-a', 'gfx90a', '-n', '110'])

  def test_arch_argument(self):
    """Test --arch argument."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx908', '-n', '120', '-f'])
    assert args.arch == 'gfx908'

  def test_num_cu_argument(self):
    """Test --num_cu argument."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '104', '-f'])
    assert args.num_cu == 104

  def test_opencl_flag(self):
    """Test --opencl flag."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f', '-c'])
    assert args.opencl is True

  def test_config_tag_argument(self):
    """Test --config_tag argument."""
    parser = get_export_db_parser()
    args = parser.parse_args([
        '--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f', '--config_tag',
        'test_tag'
    ])
    assert args.config_tag == 'test_tag'

  def test_filename_argument(self):
    """Test --filename argument."""
    parser = get_export_db_parser()
    args = parser.parse_args([
        '--session_id', '1', '-a', 'gfx90a', '-n', '110', '-f', '--filename',
        'custom.db'
    ])
    assert args.filename == 'custom.db'

  def test_version_argument(self):
    """Test --version argument."""
    parser = get_export_db_parser()
    # Note: VERSION argument doesn't have a short flag in jsonargparse
    # Just test that parser can be created - version is handled by TunaArgs
    assert parser is not None

  def test_complete_args_set(self):
    """Test parsing complete argument set."""
    parser = get_export_db_parser()
    args = parser.parse_args([
        '--session_id', '99', '-a', 'gfx90a', '-n', '110', '-f', '-c',
        '--config_tag', 'production', '--filename', 'export.fdb'
    ])
    assert args.session_id == 99
    assert args.arch == 'gfx90a'
    assert args.num_cu == 110
    assert args.find_db is True
    assert args.opencl is True
    assert args.config_tag == 'production'
    assert args.filename == 'export.fdb'


# ============================================================================
# Tests for get_update_golden_parser
# ============================================================================


@pytest.mark.unit
@pytest.mark.miopen
class TestUpdateGoldenParser:
  """Tests for update_golden subcommand parser."""

  def test_parser_creation(self):
    """Test that parser can be created successfully."""
    parser = get_update_golden_parser()
    assert parser is not None

  def test_required_golden_v_argument(self):
    """Test that --golden_v is required."""
    parser = get_update_golden_parser()
    with pytest.raises(SystemExit):
      parser.parse_args([])

  def test_golden_v_argument(self):
    """Test --golden_v argument."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220'])
    assert args.golden_v == 220

  def test_base_golden_v_argument(self):
    """Test --base_golden_v optional argument."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220', '--base_golden_v', '210'])
    assert args.base_golden_v == 210

  def test_session_id_argument(self):
    """Test --session_id optional argument."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220', '--session_id', '42'])
    assert args.session_id == 42

  def test_overwrite_flag(self):
    """Test --overwrite flag."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220', '-o'])
    assert args.overwrite is True

  def test_overwrite_default_false(self):
    """Test that --overwrite defaults to False."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220'])
    assert args.overwrite is False

  def test_create_perf_table_flag(self):
    """Test --create_perf_table flag."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220', '--create_perf_table'])
    assert args.create_perf_table is True

  def test_create_perf_table_default_false(self):
    """Test that --create_perf_table defaults to False."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220'])
    assert args.create_perf_table is False

  def test_config_type_argument(self):
    """Test --config_type argument."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['-C', 'batch_norm', '--golden_v', '220'])
    assert args.config_type == ConfigType.batch_norm

  def test_complete_args_set(self):
    """Test parsing complete argument set."""
    parser = get_update_golden_parser()
    args = parser.parse_args([
        '--golden_v', '220', '--base_golden_v', '210', '--session_id', '100',
        '-o', '--create_perf_table', '-C', 'convolution'
    ])
    assert args.golden_v == 220
    assert args.base_golden_v == 210
    assert args.session_id == 100
    assert args.overwrite is True
    assert args.create_perf_table is True
    assert args.config_type == ConfigType.convolution

  def test_base_golden_default_none(self):
    """Test that base_golden_v defaults to None."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220'])
    assert args.base_golden_v is None

  def test_session_id_default_none(self):
    """Test that session_id defaults to None."""
    parser = get_update_golden_parser()
    args = parser.parse_args(['--golden_v', '220'])
    assert args.session_id is None


# ============================================================================
# Integration tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.miopen
class TestParserIntegration:
  """Integration tests for parser functionality."""

  def test_all_parsers_can_be_created(self):
    """Test that all parsers can be created without errors."""
    parsers = [
        get_import_cfg_parser(),
        get_load_job_parser(),
        get_export_db_parser(),
        get_update_golden_parser()
    ]
    assert all(p is not None for p in parsers)

  def test_parsers_with_yaml_disabled(self):
    """Test that all parsers work with YAML disabled."""
    parsers = [
        get_import_cfg_parser(with_yaml=False),
        get_load_job_parser(with_yaml=False),
        get_export_db_parser(with_yaml=False),
        get_update_golden_parser(with_yaml=False)
    ]
    assert all(p is not None for p in parsers)

  def test_import_parser_typical_usage(self):
    """Test typical import_configs usage scenario."""
    parser = get_import_cfg_parser()
    args = parser.parse_args([
        '-f', 'configs.txt', '-t', 'production', '--mark_recurrent', '-C',
        'convolution'
    ])
    assert args.file_name == 'configs.txt'
    assert args.tag == 'production'
    assert args.mark_recurrent is True
    assert args.config_type == ConfigType.convolution

  def test_load_job_parser_typical_usage(self):
    """Test typical load_job usage scenario."""
    parser = get_load_job_parser()
    args = parser.parse_args([
        '-t', 'production', '-l', 'nightly_tuning', '--session_id', '1234',
        '-A', 'miopenConvolutionAlgoDirect', '--tunable', '-C', 'convolution'
    ])
    assert args.tag == 'production'
    assert args.label == 'nightly_tuning'
    assert args.session_id == 1234
    assert args.algo == 'miopenConvolutionAlgoDirect'
    assert args.tunable is True

  def test_export_db_parser_typical_usage(self):
    """Test typical export_db usage scenario."""
    parser = get_export_db_parser()
    args = parser.parse_args(
        ['--session_id', '1234', '-a', 'gfx90a', '-n', '110', '-f'])
    assert args.session_id == 1234
    assert args.arch == 'gfx90a'
    assert args.num_cu == 110
    assert args.find_db is True

  def test_update_golden_parser_typical_usage(self):
    """Test typical update_golden usage scenario."""
    parser = get_update_golden_parser()
    args = parser.parse_args([
        '--golden_v', '220', '--base_golden_v', '210', '--session_id', '1234',
        '-C', 'convolution'
    ])
    assert args.golden_v == 220
    assert args.base_golden_v == 210
    assert args.session_id == 1234
    assert args.config_type == ConfigType.convolution
