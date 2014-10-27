publish: package
	aws s3 sync --acl authenticated-read dist/ s3://gw-python-packages/simple/pipsy/

package:
	python setup.py sdist bdist_egg

clean:
	rm -rf dist/
