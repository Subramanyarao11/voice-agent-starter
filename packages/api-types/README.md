# @sahaayak/api-types

TypeScript types generated from the API's OpenAPI schema. Nothing here is
written by hand — regenerate after changing any FastAPI response model so a
contract change surfaces as a compile error in the web app rather than a
runtime surprise:

```bash
make types
```

That writes `openapi.json` and `src/schema.d.ts`. The schema is produced
in-process from the FastAPI app, so the API does not need to be running.
