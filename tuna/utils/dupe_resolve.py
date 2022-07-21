#!/usr/bin/env python3

from sqlalchemy.exc import IntegrityError, OperationalError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.helper import handle_op_error
from tuna.utils.logger import setup_logger

LOGGER = setup_logger('dupe_resolve')

view_perf_cfg_rep = """
create or replace view perf_cfg_rep as
select cc2.id, cc3.id as cfg from
(select cpc.id, cpc.valid as cpc_valid, cc.spatial_dim, cc.batchsize, cc.pad_h,
    cc.pad_w, cc.conv_stride_h, cc.conv_stride_w, cc.dilation_h, cc.dilation_w,
    cc.group_count, cc.conv_mode, cc.pad_mode, cc.trans_output_pad_h,
    cc.trans_output_pad_w, cc.input_tensor, cc.weight_tensor, cc.out_layout
    from conv_perf_config as cpc inner join conv_config as cc on cpc.config=cc.id where cc.valid=0) as cc2
inner join conv_config as cc3
on cc2.spatial_dim=cc3.spatial_dim and cc2.batchsize=cc3.batchsize and cc2.pad_h=cc3.pad_h
    and cc2.pad_w=cc3.pad_w and cc2.conv_stride_h=cc3.conv_stride_h and cc2.conv_stride_w=cc3.conv_stride_w
    and cc2.dilation_h=cc3.dilation_h and cc2.dilation_w=cc3.dilation_w
    and cc2.group_count=cc3.group_count and cc2.conv_mode=cc3.conv_mode
    and cc2.pad_mode=cc3.pad_mode and cc2.trans_output_pad_h=cc3.trans_output_pad_h
    and cc2.trans_output_pad_w=cc3.trans_output_pad_w and cc2.input_tensor=cc3.input_tensor
    and cc2.weight_tensor=cc3.weight_tensor and cc2.out_layout=cc3.out_layout
where cc3.spatial_dim=2 and cc3.valid=1 and cc2.cpc_valid=1
group by cc2.id, cfg;
"""

view_perf_db_rep = """
create or replace view perf_db_rep as
select cpd2.theid, cpc3.id as mcfg from
(select cpd.id as theid, cpd.valid as cpd_valid, layout, data_type, direction, bias, config, cc.*
    from conv_perf_db as cpd
    inner join conv_perf_config as cpc on cpd.miopen_config=cpc.id
    inner join conv_config as cc on cpc.config=cc.id
    where cc.valid=0) as cpd2
inner join conv_perf_config as cpc3
    on cpd2.layout=cpc3.layout and cpd2.data_type=cpc3.data_type
    and cpd2.direction=cpc3.direction and cpd2.bias=cpc3.bias
inner join conv_config as cc3
    on cc3.id=cpc3.config
    and cpd2.spatial_dim=cc3.spatial_dim and cpd2.batchsize=cc3.batchsize and cpd2.pad_h=cc3.pad_h
    and cpd2.pad_w=cc3.pad_w and cpd2.conv_stride_h=cc3.conv_stride_h and cpd2.conv_stride_w=cc3.conv_stride_w
    and cpd2.dilation_h=cc3.dilation_h and cpd2.dilation_w=cc3.dilation_w
    and cpd2.group_count=cc3.group_count and cpd2.conv_mode=cc3.conv_mode
    and cpd2.pad_mode=cc3.pad_mode and cpd2.trans_output_pad_h=cc3.trans_output_pad_h
    and cpd2.trans_output_pad_w=cc3.trans_output_pad_w and cpd2.input_tensor=cc3.input_tensor
    and cpd2.weight_tensor=cc3.weight_tensor and cpd2.out_layout=cc3.out_layout
where cc3.valid=1 and cpc3.valid=1 and cpd2.cpd_valid=1
group by cpd2.theid, mcfg;
"""


def main():
  """main"""
  with DbSession() as session:
    session.execute(view_perf_cfg_rep)
    session.commit()
    res = session.execute("select id, cfg from perf_cfg_rep").all()
    invalid = 0
    for id, cfg in res:
      try:
        query = "update conv_perf_config set config={} where id={};".format(
            cfg, id)
        print(query)
        #session.execute(query)
        #session.commit()
      except OperationalError as error:
        handle_op_error(LOGGER, error)
      except IntegrityError as error:
        session.rollback()
        LOGGER.warning('insert failed (%s)', error)
        if "Duplicate entry" in "%s" % error:
          query = "update conv_perf_config set valid=0 where id={};".format(id)
          LOGGER.warning('Invalidating entry (%s)', query)
          invalid += 1
          session.execute(query)
          session.commit()

    if invalid:
      LOGGER.warning('Invalidated %u perf_config entries', invalid)

    session.execute(view_perf_db_rep)
    session.commit()
    res = session.execute("select theid, mcfg from perf_db_rep").all()
    invalid = 0
    for id, cfg in res:
      try:
        query = "update conv_perf_db set miopen_config={} where id={};".format(
            cfg, id)
        print(query)
        session.execute(query)
        session.commit()
      except OperationalError as error:
        handle_op_error(LOGGER, error)
      except IntegrityError as error:
        session.rollback()
        LOGGER.warning('insert failed (%s)', error)
        if "Duplicate entry" in "%s" % error:
          query = "update conv_perf_db set valid=0 where id={};".format(id)
          LOGGER.warning('Invalidating entry (%s)', query)
          invalid += 1
          session.execute(query)
          session.commit()

    if invalid:
      LOGGER.warning('Invalidated %u perf_db entries', invalid)


if __name__ == '__main__':
  main()
