//! Shared configurations between instances (N-04): an instance asks the
//! host of another one for the ids of its configurations and merges the
//! Automerge documents of the shared ones through its own host, so both
//! libraries end up with the changes of both. The documents go as hex in
//! the JSON messages of the control channel. Pictures go by their SHA-256
//! name: each host names the ones its merged configuration lacks.

use electrip_core::config;
use electrip_core::host::Host;
use electrip_core::picture;
use electrip_sync::{Document, library};
use serde_json::{Value, json};
use std::io::{self, BufRead, BufReader, Lines, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::time::Duration;

/// Merging a large configuration takes a while.
const TIMEOUT: Duration = Duration::from_secs(10);

/// The reply to a sync request, `None` if `line` is none: the host
/// answers it itself, it is no command of the session.
pub(crate) fn answer(host: &mut Host, line: &str) -> Option<Result<Value, String>> {
    let request: Value = serde_json::from_str(line).ok()?;
    let result = match request["command"].as_str()? {
        "configuration_ids" => ids(host.library()).map(|ids| json!({"ids": ids})),
        "sync_configuration" => merge(host, &request),
        "picture" => picture(host, &request),
        "add_picture" => add_picture(host, &request),
        _ => return None,
    };
    Some(result.map_err(|e| e.to_string()))
}

type Error = Box<dyn std::error::Error>;

fn ids(library: &Path) -> Result<Vec<String>, Error> {
    let ids = library::ids(library)?;
    Ok(ids.into_iter().map(|(id, _)| id).collect())
}

/// Merges the `document` of the request, if any, into the configuration
/// `id` and returns its document and the pictures it lacks; the host takes
/// over the open configuration if it changed.
fn merge(host: &mut Host, request: &Value) -> Result<Value, Error> {
    let id = request["id"].as_str().ok_or("no configuration id")?;
    let library = host.library().to_path_buf();
    let (_, name) = library::ids(&library)?
        .into_iter()
        .find(|(known, _)| known == id)
        .ok_or_else(|| format!("there is no configuration with id {id}"))?;
    if let Some(hex) = request["document"].as_str() {
        let mut other = Document::load(&decode(hex).ok_or("invalid document")?)?;
        if library::merge(&library, &name, &mut other)? && name == host.session().configuration() {
            host.reload()?;
        }
    }
    let mut document = library::document(&library, &name)?;
    let missing = missing_pictures(host, &name)?;
    Ok(json!({"document": encode(&document.save()), "missing": missing}))
}

/// The pictures the locos of the configuration `name` use and the media
/// directory lacks.
fn missing_pictures(host: &Host, name: &str) -> Result<Vec<String>, Error> {
    let config = config::read(&config::path(host.library(), name))?;
    let media = host.media();
    let pictures = config.locos.iter().filter_map(|loco| loco.picture());
    let missing = pictures.filter(|name| !picture::path(&media, name).exists());
    Ok(missing.map(String::from).collect())
}

fn picture(host: &Host, request: &Value) -> Result<Value, Error> {
    let name = request["name"].as_str().ok_or("no picture name")?;
    let content = picture::content(&host.media(), name)?;
    Ok(json!({"content": encode(&content)}))
}

fn add_picture(host: &Host, request: &Value) -> Result<Value, Error> {
    let hex = request["content"].as_str().ok_or("no picture")?;
    picture::add(&host.media(), &decode(hex).ok_or("invalid picture")?)?;
    Ok(json!({}))
}

/// Merges the configurations the hosts at `local` and `peer` share.
pub fn sync(local: SocketAddr, peer: SocketAddr) -> io::Result<()> {
    let (mut local, mut peer) = (Connection::open(local)?, Connection::open(peer)?);
    let theirs = peer.ids()?;
    for id in local.ids()?.into_iter().filter(|id| theirs.contains(id)) {
        let (document, _) = local.document(&id, None)?;
        let (document, missing) = peer.document(&id, Some(document))?;
        copy_pictures(&mut local, &mut peer, &missing)?;
        let (_, missing) = local.document(&id, Some(document))?;
        copy_pictures(&mut peer, &mut local, &missing)?;
    }
    Ok(())
}

/// Copies the pictures `names` that `from` has to `to`.
fn copy_pictures(from: &mut Connection, to: &mut Connection, names: &[String]) -> io::Result<()> {
    for name in names {
        if let Ok(reply) = from.request(json!({"command": "picture", "name": name})) {
            to.request(json!({"command": "add_picture", "content": reply["content"]}))?;
        }
    }
    Ok(())
}

struct Connection {
    writer: TcpStream,
    lines: Lines<BufReader<TcpStream>>,
}

impl Connection {
    fn open(host: SocketAddr) -> io::Result<Connection> {
        let stream = TcpStream::connect_timeout(&host, crate::HOST_TIMEOUT)?;
        stream.set_read_timeout(Some(TIMEOUT))?;
        let writer = stream.try_clone()?;
        let lines = BufReader::new(stream).lines();
        Ok(Connection { writer, lines })
    }

    fn ids(&mut self) -> io::Result<Vec<String>> {
        let reply = self.request(json!({"command": "configuration_ids"}))?;
        Ok(serde_json::from_value(reply["ids"].clone())?)
    }

    /// Sends `document` to merge, if any, and returns the merged one and
    /// the pictures the host lacks.
    fn document(
        &mut self,
        id: &str,
        document: Option<String>,
    ) -> io::Result<(String, Vec<String>)> {
        let request = json!({"command": "sync_configuration", "id": id, "document": document});
        let mut reply = self.request(request)?;
        let document = reply["document"]
            .as_str()
            .ok_or(io::ErrorKind::InvalidData)?;
        Ok((
            document.into(),
            serde_json::from_value(reply["missing"].take())?,
        ))
    }

    /// The reply to `request`, skipping the states before it.
    fn request(&mut self, request: Value) -> io::Result<Value> {
        self.writer.write_all(format!("{request}\n").as_bytes())?;
        loop {
            let line = self.lines.next().ok_or(io::ErrorKind::UnexpectedEof)??;
            let message: Value = serde_json::from_str(&line)?;
            if message["type"] != "reply" {
                continue;
            }
            if message["ok"] != true {
                return Err(io::Error::other(message["error"].to_string()));
            }
            return Ok(message);
        }
    }
}

fn encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn decode(hex: &str) -> Option<Vec<u8>> {
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(hex.get(i..i + 2)?, 16).ok())
        .collect()
}

#[cfg(test)]
mod tests;
