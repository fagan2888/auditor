use std::collections::HashMap;
use std::fmt;

pub type Clause = HashMap<String, Value>;

#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum Value {
    String(String),
    Integer(u64),
    Float(f64),
    Bool(bool),
    Vec(Vec<Value>),
}

impl From<String> for Value {
    fn from(s: String) -> Value {
        Value::String(s)
    }
}

impl From<&str> for Value {
    fn from(s: &str) -> Value {
        Value::String(s.to_string())
    }
}

impl From<u64> for Value {
    fn from(i: u64) -> Value {
        Value::Integer(i)
    }
}

impl From<bool> for Value {
    fn from(b: bool) -> Value {
        Value::Bool(b)
    }
}

impl PartialEq<bool> for Value {
    fn eq(&self, rhs: &bool) -> bool {
        match &self {
            Value::Bool(b) => b == rhs,
            _ => false,
        }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, fmt: &mut fmt::Formatter) -> fmt::Result {
        let desc = match &self {
            Value::String(s) => format!("“{}”", s),
            Value::Integer(n) => format!("{}", n),
            Value::Float(n) => format!("{:.2}", n),
            Value::Bool(b) => format!("{}", b),
            Value::Vec(_) => panic!("display for Vec is not implemented yet!"),
        };
        fmt.write_str(&desc)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serialize() {
        let mut data = Clause::new();
        data.insert("level".to_string(), 100.into());

        let expected = r#"---
level: 100"#;

        let actual = serde_yaml::to_string(&data).unwrap();

        assert_eq!(actual, expected);
    }
}
