Here are some rules I'd always like you to follow:

* Whenever you add, update, or delete code ensure that you're always doing the same action as it pertains to tests. That is
  to say if you're adding new code then you should add new tests. If you update existing code you should be updating existing
  tests (if none exist, you should add some), and if you remove code then you should ensure that tests are removed/updated
  accordingly.
* Every time you make a code change you should re-run the tests. I can't provide you with a specific command to run here, as
  it is language dependent (`npm test` for Node, `cargo test` for Rust, `go test` for Go, etc).
* Whenever a change modifies a user facing interface, is a major architectural change, or changes something about the build
  process you should think about updating the project's @README.md file. If you're ever unsure if it is necessary, just ask
  me.
* Whenever any substantial code change is made (including but not limited to anything that would cause you to modify the
  @README.md file) you should update the @CLAUDE.md file in the root of the project directory. This file is for you to regain
  context quickly in the future without having to consume the entirety of the project's code.