//! Shared configurations (N-04, ADR 0003): every configuration is an
//! Automerge document, so instances that change it apart can merge their
//! changes. When two change the same field, the last merged change wins.

use automerge::{
    AutoCommit, AutoSerde, AutomergeError, ChangeHash, ObjId, ObjType, Prop, ROOT, ReadDoc,
};
use automerge::{ScalarValue, transaction::Transactable};
use electrip_core::config::Config;
use serde_json::{Map, Value};

pub mod library;

/// A configuration as an Automerge document.
pub struct Document(AutoCommit);

#[derive(Debug)]
pub enum Error {
    Automerge(AutomergeError),
    Json(serde_json::Error),
    Io(std::io::Error),
    /// A configuration id that cannot name a file.
    InvalidId(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Error::Automerge(error) => write!(f, "{error}"),
            Error::Json(error) => write!(f, "{error}"),
            Error::Io(error) => write!(f, "{error}"),
            Error::InvalidId(id) => write!(f, "invalid configuration id {id}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(error: std::io::Error) -> Self {
        Error::Io(error)
    }
}

impl From<AutomergeError> for Error {
    fn from(error: AutomergeError) -> Self {
        Error::Automerge(error)
    }
}

impl From<serde_json::Error> for Error {
    fn from(error: serde_json::Error) -> Self {
        Error::Json(error)
    }
}

impl Document {
    pub fn new(config: &Config) -> Result<Self, Error> {
        let mut document = Document(AutoCommit::new());
        document.update(config)?;
        Ok(document)
    }

    pub fn load(bytes: &[u8]) -> Result<Self, Error> {
        Ok(Document(AutoCommit::load(bytes)?))
    }

    pub fn save(&mut self) -> Vec<u8> {
        self.0.save()
    }

    pub fn heads(&mut self) -> Vec<ChangeHash> {
        self.0.get_heads()
    }

    pub fn config(&self) -> Result<Config, Error> {
        Ok(serde_json::from_value(self.json()?)?)
    }

    /// Records the fields in which `config` differs from the document.
    pub fn update(&mut self, config: &Config) -> Result<(), Error> {
        let old: Map<String, Value> = serde_json::from_value(self.json()?)?;
        let new: Map<String, Value> = serde_json::from_value(serde_json::to_value(config)?)?;
        update_map(&mut self.0, &ROOT, &old, &new)?;
        Ok(())
    }

    /// Takes over the changes of `other` that this document lacks.
    pub fn merge(&mut self, other: &mut Document) -> Result<(), Error> {
        self.0.merge(&mut other.0)?;
        Ok(())
    }

    fn json(&self) -> Result<Value, Error> {
        Ok(serde_json::to_value(AutoSerde::from(&self.0))?)
    }
}

/// Changes the value at `prop` of `obj` from `old` to `new`, going into
/// maps and lists so that only changed fields are written.
fn update(
    doc: &mut AutoCommit,
    obj: &ObjId,
    prop: Prop,
    old: Option<&Value>,
    new: &Value,
) -> Result<(), AutomergeError> {
    if old == Some(new) {
        return Ok(());
    }
    let child = match doc.get(obj, prop.clone())? {
        Some((automerge::Value::Object(_), id)) => Some(id),
        _ => None,
    };
    match (child, old, new) {
        (Some(id), Some(Value::Object(old)), Value::Object(new)) => update_map(doc, &id, old, new),
        (Some(id), Some(Value::Array(old)), Value::Array(new)) => update_list(doc, &id, old, new),
        _ => put(doc, obj, prop, new),
    }
}

fn update_map(
    doc: &mut AutoCommit,
    obj: &ObjId,
    old: &Map<String, Value>,
    new: &Map<String, Value>,
) -> Result<(), AutomergeError> {
    for key in old.keys().filter(|key| !new.contains_key(*key)) {
        doc.delete(obj, key.as_str())?;
    }
    for (key, value) in new {
        update(doc, obj, key.as_str().into(), old.get(key), value)?;
    }
    Ok(())
}

/// Keeps the equal items at both ends, so that adding or removing a loco
/// does not rewrite the locos behind it.
fn update_list(
    doc: &mut AutoCommit,
    obj: &ObjId,
    old: &[Value],
    new: &[Value],
) -> Result<(), AutomergeError> {
    let start = old.iter().zip(new).take_while(|(o, n)| o == n).count();
    let (old, new) = (&old[start..], &new[start..]);
    let end = old
        .iter()
        .rev()
        .zip(new.iter().rev())
        .take_while(|(o, n)| o == n)
        .count();
    let (old, new) = (&old[..old.len() - end], &new[..new.len() - end]);
    for (index, (old, new)) in old.iter().zip(new).enumerate() {
        update(doc, obj, Prop::Seq(start + index), Some(old), new)?;
    }
    for _ in new.len()..old.len() {
        doc.delete(obj, start + new.len())?;
    }
    for (index, value) in new.iter().enumerate().skip(old.len()) {
        insert(doc, obj, start + index, value)?;
    }
    Ok(())
}

/// Writes `value` at `prop` of `obj` as a new value.
fn put(doc: &mut AutoCommit, obj: &ObjId, prop: Prop, value: &Value) -> Result<(), AutomergeError> {
    match object_type(value) {
        Some(object_type) => {
            let id = doc.put_object(obj, prop, object_type)?;
            fill(doc, &id, value)
        }
        None => doc.put(obj, prop, scalar(value)),
    }
}

/// Inserts `value` into the list `obj` at `index`.
fn insert(
    doc: &mut AutoCommit,
    obj: &ObjId,
    index: usize,
    value: &Value,
) -> Result<(), AutomergeError> {
    match object_type(value) {
        Some(object_type) => {
            let id = doc.insert_object(obj, index, object_type)?;
            fill(doc, &id, value)
        }
        None => doc.insert(obj, index, scalar(value)),
    }
}

/// Fills the new, empty map or list `obj` with `value`.
fn fill(doc: &mut AutoCommit, obj: &ObjId, value: &Value) -> Result<(), AutomergeError> {
    match value {
        Value::Object(map) => update_map(doc, obj, &Map::new(), map),
        Value::Array(items) => update_list(doc, obj, &[], items),
        _ => Ok(()),
    }
}

fn object_type(value: &Value) -> Option<ObjType> {
    match value {
        Value::Object(_) => Some(ObjType::Map),
        Value::Array(_) => Some(ObjType::List),
        _ => None,
    }
}

fn scalar(value: &Value) -> ScalarValue {
    match value {
        Value::Bool(b) => ScalarValue::Boolean(*b),
        Value::Number(n) => match (n.as_u64(), n.as_i64()) {
            (Some(u), _) => ScalarValue::Uint(u),
            (None, Some(i)) => ScalarValue::Int(i),
            _ => ScalarValue::F64(n.as_f64().unwrap_or_default()),
        },
        Value::String(s) => ScalarValue::Str(s.as_str().into()),
        _ => ScalarValue::Null,
    }
}

#[cfg(test)]
mod tests;
