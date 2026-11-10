//! The audio targets of the host (N-05): a loco plays on the instance its
//! configuration names while that instance is connected, else on the host.

use super::{Audio, AudioEvent, AudioSink, ChannelId};
use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::time::Duration;

/// Sends an audio event to another instance; `false` when it is gone.
pub type Remote = Box<dyn FnMut(&AudioEvent) -> bool + Send>;

/// Where a loco plays: the instance, `None` the host, and its device.
type Place = (Option<String>, Option<String>);

pub(crate) struct Targets {
    local: Audio,
    remote: HashMap<String, Remote>,
    /// Where each loco plays now.
    placed: HashMap<u32, Place>,
    /// The channels the locos used, to silence them when a loco moves or
    /// is gone.
    channels: HashSet<ChannelId>,
}

impl Targets {
    pub(crate) fn new(local: Audio) -> Self {
        Targets {
            local,
            remote: HashMap::new(),
            placed: HashMap::new(),
            channels: HashSet::new(),
        }
    }

    pub(crate) fn add(&mut self, instance: String, remote: Remote) {
        self.remote.insert(instance, remote);
    }

    pub(crate) fn remove(&mut self, instance: &str) {
        self.remote.remove(instance);
    }

    /// Plays the loco on the device of the instance, if it is connected;
    /// else on the default device of the host. A loco that moves to
    /// another instance falls silent on the old one.
    pub(crate) fn route(&mut self, loco: u32, instance: Option<&str>, device: Option<&str>) {
        let connected = instance.is_none_or(|i| self.remote.contains_key(i));
        let place = if connected {
            (instance.map(String::from), device.map(String::from))
        } else {
            (None, None)
        };
        let before = self.placed.insert(loco, place.clone());
        if before.as_ref() == Some(&place) {
            return;
        }
        if let (Some(instance), false) = (instance, connected) {
            eprintln!(
                "ERROR the instance {instance} is not connected, the host plays the sounds of loco {loco}"
            );
        }
        if let Some((old, _)) = before.filter(|b| b.0 != place.0) {
            self.silence(loco, &old);
        }
        let (instance, device) = place;
        self.send(&instance, &AudioEvent::Route { loco, device });
    }

    /// Silences the locos that are not among `locos`: removed ones and
    /// those of a guest that left.
    pub(crate) fn retain(&mut self, locos: &HashSet<u32>) {
        let gone: Vec<_> = self
            .placed
            .keys()
            .filter(|l| !locos.contains(l))
            .copied()
            .collect();
        for loco in gone {
            if let Some((instance, _)) = self.placed.remove(&loco) {
                self.silence(loco, &instance);
            }
        }
    }

    /// Stops the channels the loco used on the instance.
    fn silence(&mut self, loco: u32, instance: &Option<String>) {
        let used: Vec<_> = self
            .channels
            .iter()
            .filter(|c| c.loco == loco)
            .copied()
            .collect();
        for channel in used {
            self.channels.remove(&channel);
            self.send(instance, &AudioEvent::Stop { channel });
        }
    }

    /// Sends the event of the channel to where its loco plays.
    fn dispatch(&mut self, channel: ChannelId, event: AudioEvent) {
        self.channels.insert(channel);
        let instance = self.placed.get(&channel.loco).and_then(|p| p.0.clone());
        self.send(&instance, &event);
    }

    /// Sends the event to the instance, `None` the host; the host plays
    /// it when the instance is gone.
    fn send(&mut self, instance: &Option<String>, event: &AudioEvent) {
        let remote = instance
            .as_ref()
            .and_then(|i| Some((i, self.remote.get_mut(i)?)));
        if let Some((instance, remote)) = remote {
            if remote(event) {
                return;
            }
            eprintln!("ERROR the instance {instance} is gone, the host plays its sounds");
            self.remote.remove(instance);
        }
        event.apply(&mut *self.local);
    }
}

impl AudioSink for Targets {
    /// The host knows the sounds of all instances.
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        self.local.length(sound)
    }

    fn queue(&mut self, channel: ChannelId, sound: &Path) {
        let sound = sound.into();
        self.dispatch(channel, AudioEvent::Queue { channel, sound });
    }

    fn play(&mut self, channel: ChannelId, sound: &Path, delay: Duration) {
        let sound = sound.into();
        self.dispatch(
            channel,
            AudioEvent::Play {
                channel,
                sound,
                delay,
            },
        );
    }

    fn stop(&mut self, channel: ChannelId) {
        self.dispatch(channel, AudioEvent::Stop { channel });
    }

    fn fade_in(&mut self, channel: ChannelId, sound: &Path, fade: Duration) {
        let sound = sound.into();
        self.dispatch(
            channel,
            AudioEvent::FadeIn {
                channel,
                sound,
                fade,
            },
        );
    }

    fn fade_out(&mut self, channel: ChannelId, fade: Duration) {
        self.dispatch(channel, AudioEvent::FadeOut { channel, fade });
    }

    fn devices(&mut self) -> Vec<String> {
        self.local.devices()
    }
}

#[cfg(test)]
mod tests;
