pytest_bin := py.test
pytest_opts := --doctest-modules --ignore=rhino/vendor
coverage_opts := --cov=rhino --cov=examples --cov-report=term --cov-report=html
test_cmd := $(pytest_bin) $(pytest_opts)
test_targets := test/ rhino/

test:
	$(test_cmd) $(test_targets)

cover:
	$(test_cmd) $(coverage_opts) $(test_targets)

.PHONY: test cover

README.rst: README.mkd
	pandoc --from=markdown --to=rst $< > $@
