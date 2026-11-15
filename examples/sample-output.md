== examples/good.yaml ==
OK — 1 file(s) checked, every mapping key is sorted.

== examples/bad.yaml ==
FAIL examples/bad.yaml: line 4 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 7 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 9 key "banana" is out of order — it sorts before "mango"
Checked 1 file(s), 3 key(s) out of order in 1 file(s).

== examples/edge.yaml ==
OK — 1 file(s) checked, every mapping key is sorted.

== examples/ : the whole folder ==
FAIL examples/bad.yaml: line 4 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 7 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 9 key "banana" is out of order — it sorts before "mango"
Checked 3 file(s), 3 key(s) out of order in 1 file(s).
