package worker

import "context"

type Runner interface {
	Run(ctx context.Context) error
}

type Service struct {
	name string
}

const (
	DefaultName = "svc"
	MaxRetries  = 3
)

var (
	GlobalEnabled = true
	globalVersion = "dev"
)

func Build(name string) *Service {
	return &Service{name: name}
}

func (s *Service) Run(ctx context.Context) error {
	_ = ctx
	return nil
}
