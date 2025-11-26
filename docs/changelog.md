---
## [unreleased]

### Bug Fixes

- install git-cliff and use config in changelog workflow (#8) - ([7a54750](https://github.com/JacobCoffee/litestar-storages/commit/7a547501919a438405e1707b482e0c8a68603a0a)) - Jacob Coffee

### Features

- Make Litestar optional, add cookbook & example apps (Phase 7-8) (#20) - ([8dc2522](https://github.com/JacobCoffee/litestar-storages/commit/8dc2522d2e7cd658d36f7d57d51a6c50b7d2c5c9)) - Jacob Coffee

### Ci

- add pytest-rerunfailures for flaky emulator tests (#12) - ([ef5dc51](https://github.com/JacobCoffee/litestar-storages/commit/ef5dc516a11381ee770333d4ab1c6e5278490ffa)) - Jacob Coffee
- group dependabot updates  (#14) - ([51ad0b5](https://github.com/JacobCoffee/litestar-storages/commit/51ad0b588755e5e3427c0c3aeb208e4da11dc3a7)) - Jacob Coffee

---
## [0.1.0] - 2025-11-26

### Bug Fixes

- convert markdown code blocks to RST in docstrings - ([678ba52](https://github.com/JacobCoffee/litestar-storages/commit/678ba5260170d3ac41e89302756756c4f19ba7b7)) - Jacob Coffee
- correct path parameter handling in example apps - ([0558df1](https://github.com/JacobCoffee/litestar-storages/commit/0558df14d72f35dd091c200d4835187e38ee0f9e)) - Jacob Coffee
- resolve CI workflow issues (#7) - ([77a2e82](https://github.com/JacobCoffee/litestar-storages/commit/77a2e82225557a7e32508c6f3a2ea5b37b7bc837)) - Jacob Coffee

### Documentation

- update PLAN.md to mark lifespan management complete - ([d52f77c](https://github.com/JacobCoffee/litestar-storages/commit/d52f77c754240c0b2c4803c37d0b70f46084f10f)) - Jacob Coffee
- add comprehensive API reference documentation - ([68c1228](https://github.com/JacobCoffee/litestar-storages/commit/68c12284316843b18c678a9253d02f33e9e2a174)) - Jacob Coffee
- update PLAN.md to mark Phase 5 complete - ([e1d4caa](https://github.com/JacobCoffee/litestar-storages/commit/e1d4caabe3ebf970cea05a438b632c0caa1cab5a)) - Jacob Coffee
- update PLAN.md with Phase 6 progress - ([66fa231](https://github.com/JacobCoffee/litestar-storages/commit/66fa2319f9d3bc48c75a3ae1e47b37252af374c8)) - Jacob Coffee
- add comprehensive documentation for advanced features - ([a68567b](https://github.com/JacobCoffee/litestar-storages/commit/a68567bea1ef1c6c1221ae6f5d03636b08e4fcc1)) - Jacob Coffee
- add comprehensive library comparison documentation - ([5316db5](https://github.com/JacobCoffee/litestar-storages/commit/5316db50e6ad52891be697f83f384bb74b1109a8)) - Jacob Coffee
- fix DTO inheritance rendering in Sphinx - ([ed349bb](https://github.com/JacobCoffee/litestar-storages/commit/ed349bba51dadc15f552d69f6e6b6e9f15413c3d)) - Jacob Coffee
- update PLAN.md - all phases complete, 99% coverage - ([c773f4c](https://github.com/JacobCoffee/litestar-storages/commit/c773f4c5e3a57f10e36fea730c6b494ec9735142)) - Jacob Coffee

### Features

- **(azure)** add multipart upload and progress callback support - ([677dd78](https://github.com/JacobCoffee/litestar-storages/commit/677dd78841f7e56cd09ba11f6651bd92d101b751)) - Jacob Coffee
- **(gcs)** add multipart upload and progress callback support - ([a4667a5](https://github.com/JacobCoffee/litestar-storages/commit/a4667a5544ee2d5772c88cba7db258b9030077fd)) - Jacob Coffee
- v0.1.0 foundation - async storage library for Litestar - ([cfebeef](https://github.com/JacobCoffee/litestar-storages/commit/cfebeefd66e59bf5b804724160c67f840fd9d539)) - Jacob Coffee
- add lifespan management for storage backends - ([6e0f3c7](https://github.com/JacobCoffee/litestar-storages/commit/6e0f3c7a6570fe17c863d6be1bef886e90b46537)) - Jacob Coffee
- add Azure Blob Storage and Google Cloud Storage backends - ([fddb2f1](https://github.com/JacobCoffee/litestar-storages/commit/fddb2f16e935bb84c26d9aecdef0c4e0e806a823)) - Jacob Coffee
- add advanced features - retry, multipart uploads, progress callbacks - ([abf61ab](https://github.com/JacobCoffee/litestar-storages/commit/abf61ab63c80f2bb59d8a4f9eb471b785d4c81fd)) - Jacob Coffee
- add performance benchmarking script - ([0b6b37e](https://github.com/JacobCoffee/litestar-storages/commit/0b6b37e48487dc48fa73ecb36d114a7ed11b8987)) - Jacob Coffee

### Miscellaneous Chores

- **(azure)** add pragma no cover for untestable paths - ([29b6804](https://github.com/JacobCoffee/litestar-storages/commit/29b6804e6022d8601f24c741061632de03bf085b)) - Jacob Coffee
- **(retry)** add pragma no cover for unreachable code - ([83d5c7a](https://github.com/JacobCoffee/litestar-storages/commit/83d5c7aba8f09a3a893ceeafb1e6f7693e23e4f7)) - Jacob Coffee
- **(s3)** add pragma no cover for SDK error handlers - ([52b3539](https://github.com/JacobCoffee/litestar-storages/commit/52b3539a4090ec903fdef433695219783b5bb639)) - Jacob Coffee

### Performance

- optimize test suite with session-scoped fixtures - ([612f167](https://github.com/JacobCoffee/litestar-storages/commit/612f1676af555aa10be0899d77ebceff33e2127e)) - Jacob Coffee

### Security

- add zizmor workflow security scanning - ([7e02917](https://github.com/JacobCoffee/litestar-storages/commit/7e0291745dd7115645796e3cbefd44edc54b929c)) - Jacob Coffee

### Tests

- **(azure)** improve coverage from 52% to 95% - ([4d40d62](https://github.com/JacobCoffee/litestar-storages/commit/4d40d6220820c8070ce8d8901b60d00c19caef08)) - Jacob Coffee
- **(base)** achieve 100% coverage with MinimalStorage - ([5ec87ba](https://github.com/JacobCoffee/litestar-storages/commit/5ec87ba12e0cfab08054e45b62ff52d3d28f4f70)) - Jacob Coffee
- **(filesystem)** improve coverage to 97% - ([5e933d0](https://github.com/JacobCoffee/litestar-storages/commit/5e933d0dee18246f39facb0498de04d0ec4e110c)) - Jacob Coffee
- **(gcs)** improve coverage from 73% to 100% - ([eb4e1fe](https://github.com/JacobCoffee/litestar-storages/commit/eb4e1fed3d35dd679c9a8b3664a71c69446edc30)) - Jacob Coffee
- **(memory)** achieve 100% coverage - ([b692a99](https://github.com/JacobCoffee/litestar-storages/commit/b692a99e09c7c70fffa7bf2b7cd20777f28e2439)) - Jacob Coffee
- **(retry)** improve coverage to 95% - ([8827a14](https://github.com/JacobCoffee/litestar-storages/commit/8827a1436810260fee5890849057a5f7dcc88f74)) - Jacob Coffee
- **(s3)** improve coverage from 57% to 89% - ([2f571a3](https://github.com/JacobCoffee/litestar-storages/commit/2f571a3dcb236b12fba7aa7b0d7ac7cdb0521503)) - Jacob Coffee
- fix unused import in retry tests - ([576d5bc](https://github.com/JacobCoffee/litestar-storages/commit/576d5bc791c32c53c3d3cfb7b9140e7168306540)) - Jacob Coffee
- add comprehensive tests for core modules - ([ff2305c](https://github.com/JacobCoffee/litestar-storages/commit/ff2305c6cbff54955b7b3086e8ff95f5906cd8a8)) - Jacob Coffee

``litestar-storages`` Changelog
