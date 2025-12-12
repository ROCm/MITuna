###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
"""Additional merge_db branch coverage."""
import sqlite3

import pytest

import tuna.miopen.subcmd.merge_db as merge_db


def test_parse_args_requires_type(monkeypatch):
  monkeypatch.setattr(merge_db.argparse._sys, 'argv',
                      ['prog', '-m', 'master', '-t', 'target'])
  with pytest.raises(SystemExit):
    merge_db.parse_args()


@pytest.mark.parametrize("master,key,vals,keep_keys", [
    (None, 'k', {}, False),
    ({}, '', {}, False),
    ({}, 'k', None, False),
])
def test_target_merge_validation(master, key, vals, keep_keys):
  with pytest.raises(ValueError):
    merge_db.target_merge(master, key, vals, keep_keys)


def test_is_float():
  assert merge_db.is_float('1.0')
  assert merge_db.is_float('3') is True
  assert merge_db.is_float('bad') is False


def test_merge_text_file_copy_only(tmp_path):
  master = tmp_path / "gfx900.HIP.fdb.txt"
  target = tmp_path / "target.HIP.fdb.txt"
  master.write_text("a=1:1.0\n", encoding="utf-8")
  target.write_text("b=2:2.0\n", encoding="utf-8")
  res = merge_db.merge_text_file(str(master),
                                 copy_only=True,
                                 keep_keys=False,
                                 target_file=str(target))
  assert res is None


def test_merge_sqlite_bin_cache(tmp_path):
  dest = tmp_path / "gfx900.kdb"
  src = tmp_path / "src.kdb"
  for path in [dest, src]:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE kern_db (kernel_name TEXT, kernel_args TEXT, kernel_blob BLOB, kernel_hash TEXT, uncompressed_size INT, PRIMARY KEY(kernel_name, kernel_args))"
    )
    conn.commit()
    cur.close()
    conn.close()

  # preload destination with one row to force duplicate path
  conn = sqlite3.connect(dest)
  conn.execute("INSERT INTO kern_db VALUES('k','a',x'00','h',1)")
  conn.commit()
  conn.close()

  conn_src = sqlite3.connect(src)
  conn_src.execute("INSERT INTO kern_db VALUES('k','a',x'00','h',1)")
  conn_src.commit()
  conn_src.close()

  conn_dest = sqlite3.connect(dest)
  merge_db.merge_sqlite_bin_cache(conn_dest, [str(src)])
  cur = conn_dest.cursor()
  cur.execute("SELECT count(*) FROM kern_db")
  count = cur.fetchone()[0]
  cur.close()
  conn_dest.close()
  assert count == 1


def test_get_file_list_filters(tmp_path):
  master_dir = tmp_path / "dir"
  master_dir.mkdir()
  (master_dir / "gfx803_36.HIP.fdb.txt").write_text("", encoding="utf-8")
  (master_dir / "ignore.txt").write_text("", encoding="utf-8")
  args = merge_db.argparse.Namespace(master_file=str(master_dir),
                                     find_db=True,
                                     bin_cache=False,
                                     perf_db=False,
                                     copy_only=False,
                                     keep_keys=False,
                                     target_file="")
  files = merge_db.get_file_list(args)
  assert len(files) == 1
