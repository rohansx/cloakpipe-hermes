// Cedar policy for the starter contract. Default deny: every tool needs a
// permit; the forbids on top refuse the calls a prompt injection goes for.
// A satisfied forbid refuses the call as policy_denied with the @id below.

// Ordinary commands run; the ones listed under sudo-and-rm-rf need a human instead.
@id("terminal")
permit (principal == Release::"hermes", action == Action::"terminal", resource)
unless {
  resource.args.command like "sudo *" || resource.args.command like "* sudo *" ||
  resource.args.command like "*rm -rf*" || resource.args.command like "*mkfs*" ||
  resource.args.command like "*git push --force*" || resource.args.command like "*git push -f*"
};

@id("process-manage")
permit (principal == Release::"hermes", action == Action::"process_manage", resource);

@id("read-file")
permit (principal == Release::"hermes", action == Action::"read_file", resource);

@id("write-file")
permit (principal == Release::"hermes", action == Action::"write_file", resource);

@id("patch")
permit (principal == Release::"hermes", action == Action::"patch", resource);

@id("execute-code")
permit (principal == Release::"hermes", action == Action::"execute_code", resource);

// Pipe-to-shell installs: curl ... | sh, wget ... | bash, and the python/perl variants.
@id("no-pipe-to-shell")
forbid (principal, action == Action::"terminal", resource)
when {
  (resource.args.command like "*curl*|*sh*" || resource.args.command like "*wget*|*sh*" ||
   resource.args.command like "*curl*|*python*" || resource.args.command like "*wget*|*python*")
};

// Credentials never reach the model: ssh keys, cloud credentials, .env, Hermes's auth store.
@id("no-credential-reads")
forbid (principal, action == Action::"terminal", resource)
when {
  resource.args.command like "*.ssh/*" || resource.args.command like "*.aws/*" ||
  resource.args.command like "*/.env*" || resource.args.command like "*auth.json*" ||
  resource.args.command like "*.gnupg/*" || resource.args.command like "*.netrc*"
};

@id("no-credential-files")
forbid (principal, action == Action::"read_file", resource)
when {
  resource.args.path like "*.ssh/*" || resource.args.path like "*.aws/*" ||
  resource.args.path like "*/.env*" || resource.args.path like "*auth.json*" ||
  resource.args.path like "*.gnupg/*" || resource.args.path like "*.netrc*"
};

// The agent does not edit its own guard rails: Hermes config, hooks and plugins.
@id("no-self-modification")
forbid (principal, action in [Action::"write_file", Action::"patch"], resource)
when {
  resource.args.path like "*/.hermes/config.yaml" || resource.args.path like "*/.hermes/hooks/*" ||
  resource.args.path like "*/.hermes/plugins/*" || resource.args.path like "*/.hermes/plugin-data/cloakpipe/*" ||
  resource.args.path like "*/.hermes/hermes-agent/*" || resource.args.path like "*/.claude/settings*"
};

// Privilege escalation and destructive filesystem commands need a human.
@id("sudo-and-rm-rf")
@approval("hermes:owner")
permit (principal == Release::"hermes", action == Action::"terminal", resource)
when {
  resource.args.command like "sudo *" || resource.args.command like "* sudo *" ||
  resource.args.command like "*rm -rf*" || resource.args.command like "*mkfs*" ||
  resource.args.command like "*git push --force*" || resource.args.command like "*git push -f*"
};
