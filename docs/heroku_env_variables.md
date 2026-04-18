heroku labs:enable runtime-dyno-metadata -a open-accountant

heroku labs:enable runtime-dyno-build-metadata -a open-accountant

The following dyno metadata are available:

| Name | Description | Example |
| --- | --- | --- |
| `HEROKU_APP_ID` | The unique identifier for the application. | `"9daa2797-e49b-4624-932f-ec3f9688e3da"` |
| `HEROKU_APP_NAME` | The application name. | `"example-app"` |
| `HEROKU_APP_DEFAULT_DOMAIN_NAME` | The default DNS hostname for the app. | `"example-app-1234567890ab.herokuapp.com"` |
| `HEROKU_DYNO_ID` | The dyno identifier. This metadata is not yet available in Private Spaces nor the Container Registry. | `"1vac4117-c29f-4312-521e-ba4d8638c1ac"` |
| `HEROKU_RELEASE_CREATED_AT` | The time and date the release was created. | `"2015-04-02T18:00:42Z"` |
| `HEROKU_RELEASE_VERSION` | The identifier for the current release. | `"v42"` |
| `HEROKU_SLUG_COMMIT` | The commit hash for the current release. This field is deprecated. Use `HEROKU_BUILD_COMMIT` instead. | `"2c3a0b24069af49b3de35b8e8c26765c1dba9ff0"` |
| `HEROKU_SLUG_DESCRIPTION` | The description of the current release. This field is deprecated. Use `HEROKU_BUILD_DESCRIPTION` instead. | `"Deploy 2c3a0b2"` |
| `HEROKU_BUILD_COMMIT` | The commit hash for the current build.* | `"2c3a0b24069af49b3de35b8e8c26765c1dba9ff0"` |
| `HEROKU_BUILD_DESCRIPTION` | The description of the current build.* | `"Deploy 2c3a0b2"` |

Config vars with an asterisk (*) in the description are available with the runtime-dyno-build-metadata flag.