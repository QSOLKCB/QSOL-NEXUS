use std::collections::BTreeMap;

#[derive(Debug, Clone, Default)]
pub struct VariableBook {
    values: BTreeMap<String, String>,
}

impl VariableBook {
    pub fn set(&mut self, name: &str, value: &str) -> Result<(), String> {
        let key = normalize_variable(name)?;
        self.values.insert(key, value.to_string());
        Ok(())
    }

    pub fn unset(&mut self, name: &str) -> Result<bool, String> {
        let key = normalize_variable(name)?;
        Ok(self.values.remove(&key).is_some())
    }

    pub fn get(&self, name: &str) -> Option<&str> {
        let key = name.trim().trim_start_matches('%').to_ascii_lowercase();
        self.values.get(&key).map(String::as_str)
    }

    pub fn list(&self) -> Vec<(String, String)> {
        self.values
            .iter()
            .map(|(name, value)| (format!("%{name}"), value.clone()))
            .collect()
    }

    pub fn expand(&self, text: &str) -> String {
        let mut out = text.to_string();
        let mut vars: Vec<_> = self.values.iter().collect();
        vars.sort_by_key(|(name, _)| std::cmp::Reverse(name.len()));
        for (name, value) in vars {
            out = replace_token(&out, &format!("%{name}"), value);
        }
        out
    }
}

fn normalize_variable(name: &str) -> Result<String, String> {
    let key = name.trim().trim_start_matches('%').to_ascii_lowercase();
    if key.is_empty() {
        return Err("variable name cannot be empty".to_string());
    }
    if !key
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-')
    {
        return Err("variable names may contain only ASCII letters, digits, '_' and '-'".to_string());
    }
    Ok(key)
}

#[derive(Debug, Clone, Copy)]
pub struct IdentifierContext<'a> {
    pub me: &'a str,
    pub channel: &'a str,
    pub mode: &'a str,
    pub region: &'a str,
    pub topic: &'a str,
}

pub fn expand_identifiers(text: &str, context: IdentifierContext<'_>, args_text: &str) -> String {
    let args: Vec<&str> = args_text.split_whitespace().collect();
    let mut out = text
        .replace("$me", context.me)
        .replace("$chan", context.channel)
        .replace("$mode", context.mode)
        .replace("$region", context.region)
        .replace("$topic", context.topic);

    for index in (1..=9).rev() {
        let range_token = format!("${index}-");
        let range_value = if index <= args.len() {
            args[index - 1..].join(" ")
        } else {
            String::new()
        };
        out = out.replace(&range_token, &range_value);

        let token = format!("${index}");
        let value = args.get(index - 1).copied().unwrap_or("");
        out = out.replace(&token, value);
    }
    out
}

fn replace_token(input: &str, token: &str, replacement: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut rest = input;
    while let Some(index) = rest.find(token) {
        out.push_str(&rest[..index]);
        let after = &rest[index + token.len()..];
        let boundary_ok = after
            .chars()
            .next()
            .map(|ch| !(ch.is_ascii_alphanumeric() || ch == '_' || ch == '-'))
            .unwrap_or(true);
        if boundary_ok {
            out.push_str(replacement);
            rest = after;
        } else {
            out.push_str(token);
            rest = after;
        }
    }
    out.push_str(rest);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn variables_expand_without_partial_name_collisions() {
        let mut vars = VariableBook::default();
        vars.set("%weapon", "a large trout").unwrap();
        vars.set("%weapon2", "a haddock").unwrap();
        assert_eq!(vars.expand("with %weapon / %weapon2"), "with a large trout / a haddock");
    }

    #[test]
    fn identifiers_expand_room_and_positional_context() {
        let context = IdentifierContext {
            me: "Trent",
            channel: "#commons",
            mode: "meme_casual",
            region: "commons",
            topic: "Best fish for model discipline?",
        };
        assert_eq!(
            expand_identifiers("/me $me slaps $1 in $chan with $2- [$mode/$region]", context, "Grok a large trout"),
            "/me Trent slaps Grok in #commons with a large trout [meme_casual/commons]"
        );
    }
}
