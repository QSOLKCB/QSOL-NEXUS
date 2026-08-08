# Third-Party Components and Model Fixtures

QSOL NEXUS source code and original documentation in this repository are licensed under the Apache License 2.0 unless a file explicitly states otherwise.

Third-party software, model weights, services, trademarks, and APIs retain their own licences and terms. Referencing, downloading, or interoperating with a third-party model does not relicense that model under the NEXUS Apache-2.0 licence.

## Ollama integration fixtures

The alpha3 CI workflow uses Ollama to download two small model fixtures at test time:

```text
qwen2.5:0.5b
llama3.2:1b
```

The model weights are **not committed to or distributed from this repository**.

### Qwen2.5-0.5B

Upstream: Qwen / Alibaba Cloud

The Qwen team documents Qwen2.5-0.5B as licensed under Apache License 2.0.

NEXUS uses it only as a test-time model dependency pulled through Ollama.

### Llama 3.2 1B

Upstream: Meta

Llama 3.2 1B is made available under Meta's applicable Llama licence/terms rather than the NEXUS Apache-2.0 licence.

NEXUS uses it only as a test-time model dependency pulled through Ollama. Its inclusion in a test workflow does not place the model weights under Apache-2.0 and does not make them part of the NEXUS distribution.

## Ollama

Ollama is a separate third-party runtime. NEXUS does not vendor Ollama source or binaries in this repository. The CI workflow installs a pinned Ollama release at test time.

## Python keyring (optional)

The `keyring` package is an optional installation extra used to access supported OS credential stores. It is not required for the standard-library runtime or test suite and is not vendored in this repository.

Upstream: <https://pypi.org/project/keyring/>

The upstream project publishes its own MIT / Python Software Foundation licensing terms. Installing `qsol-nexus-runtime[keyring]` does not relicense keyring under the NEXUS Apache-2.0 licence.

## Provider and model names

Names such as OpenAI, Claude, Gemini, Grok, Ollama, Qwen, and Llama are used solely for interoperability, testing, and architecture documentation. Their names and trademarks remain the property of their respective owners.

## Distribution guidance

When redistributing NEXUS itself, comply with the repository's Apache-2.0 `LICENSE` and `NOTICE` requirements.

When separately redistributing any third-party model, runtime, library, or bundled dependency, comply with that component's own licence and terms as well.

This file is informational project documentation, not legal advice.
