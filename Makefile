.PHONY: clean package publish sync


publish: package sync clean

sync:
	aws s3 sync --acl authenticated-read dist/ s3://gw-python-packages/simple/pipsy/

package:
	python setup.py sdist

clean:
	rm -rf dist/
	rm -rf build/
