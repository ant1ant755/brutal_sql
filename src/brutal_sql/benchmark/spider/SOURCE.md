# Spider dataset source

| | |
| --- | --- |
| Dataset | Spider 1.0 (Yale Semantic Parsing and Text-to-SQL Challenge) |
| Homepage | https://yale-lily.github.io/spider |
| Download (linked from the homepage) | https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view |
| URL the script uses | `https://drive.usercontent.google.com/download?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J&export=download&confirm=t` |
| File | `spider_data.zip`, 205,800,266 bytes |
| SHA-256 | `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b` |
| Version | newest entry in the archive's README: 08/03/2020 (`tables.json` fix for `scholar` and `formula_1`); archive folder dated 2024-09-12 |
| Downloaded and hash pinned | 2026-11-28 |
| Licence | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode) |

The authors don't publish a checksum. The hash above is the one we downloaded
and pinned; `fetch.py` refuses any other file.

## What the archive holds

`fetch.py` unpacks it into `data/spider/spider_data/` (gitignored), skipping
macOS metadata (`__MACOSX/`, `.DS_Store`):

- `train_spider.json` (7,000 examples, 140 databases), `train_others.json`
  (1,659 examples, 6 databases), `dev.json` (1,034 examples, 20 databases),
  `test.json`
- `tables.json` and `test_tables.json`: schemas of every database
- `train_gold.sql`, `dev_gold.sql`, `test_gold.sql`
- `database/<db_id>/<db_id>.sqlite` (166 databases) and
  `test_database/<db_id>/<db_id>.sqlite` (206), most with a `schema.sql`

## Licence and attribution

Spider is distributed under **CC BY-SA 4.0**. Anything we derive from it
(Postgres schemas converted from Spider databases, rewritten SQL, benchmark
records with `source: spider`) keeps that licence. Those records carry
`"licence": "CC BY-SA 4.0"`.

The dataset's README asks users to cite the Spider paper, Finegan-Dollak et
al. (2018), and the original datasets behind `train_others.json`
(Restaurants, GeoQuery, Scholar, Academic, IMDB, Yelp). The full BibTeX list is
in `data/spider/spider_data/README.txt` after fetching. The two main entries:

```bibtex
@inproceedings{Yu&al.18c,
  year      = 2018,
  title     = {Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task},
  booktitle = {EMNLP},
  author    = {Tao Yu and Rui Zhang and Kai Yang and Michihiro Yasunaga and Dongxu Wang and Zifan Li and James Ma and Irene Li and Qingning Yao and Shanelle Roman and Zilin Zhang and Dragomir Radev}
}

@InProceedings{P18-1033,
  author    = {Catherine Finegan-Dollak and Jonathan K. Kummerfeld and Li Zhang and Karthik Ramanathan and Sesh Sadasivam and Rui Zhang and Dragomir Radev},
  title     = {Improving Text-to-SQL Evaluation Methodology},
  booktitle = {Proceedings of the 56th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  year      = {2018},
  pages     = {351--360},
  url       = {http://aclweb.org/anthology/P18-1033}
}
```

Attribution line for reports and derived files:

> Contains data from Spider (Yu et al., 2018, https://yale-lily.github.io/spider),
> licensed CC BY-SA 4.0. Changes: converted to PostgreSQL.

## Fetching

```bash
poetry run python -m brutal_sql.benchmark.spider.fetch
git status --short data/   # prints nothing: data/ is gitignored
```
